import sys
import os
import subprocess
from subprocess import PIPE, Popen
from Bio import SeqIO
from datetime import datetime
import re
from .config import current_dir

if os.name == 'posix':
	# im on a linux machine
	bowtie_path = os.path.abspath(os.path.join(current_dir, 'executables', 'bowtie2-2.2.8-linux'))
	bowtie_suffix = ""
elif os.name == 'nt':
	# im on a windows machine
	bowtie_path = os.path.abspath(os.path.join(current_dir, 'executables', 'bowtie2-2.2.8-windows'))
	bowtie_suffix = ".exe"
elif os.name == 'mac':
	print('oops ya')
else:
	raise Exception("I was not expecting this: " + os.name)


def build_reference(input_fasta, ref_name, ref_path=None):
	input_fasta = os.path.abspath(input_fasta)

	if not os.path.isfile(input_fasta):
		raise Exception('The provided input file does not exist')
	if ref_path is None:
		ref_name = os.path.join(os.path.dirname(input_fasta), os.path.basename(ref_name))
	else:
		if not os.path.isdir(ref_path):
			os.makedirs(ref_path)
		ref_name = os.path.join(ref_path, os.path.basename(ref_name))

	execute_call = ' '.join([os.path.join(bowtie_path, "bowtie2-build"), '"' + input_fasta + '"', '"' + ref_name + '"', ' --quiet'])
	process_worked = subprocess.call(
		execute_call,
		stderr=subprocess.STDOUT,
		shell=True
	)
	if process_worked > 0:
		raise Exception('Something went wrong when building the database')
	return os.path.join(os.path.dirname(input_fasta), ref_name)


def bowtie2(fastq_files, references, paired_seqs, sam_file_name, bowtie_ref_name=None, working_directory=None, include_phix=True, phix_filter=False, threads=2, options=[]):
	"""
		Wrapper function for running bowtie2 from within python

		Args:
			fastq_files (list of strings): location of all the input seq files that will be aligned to references
			references (list of tuple OR a location to fasta file name):
				IF list of types then the format should be [(reference name, sequence), ...]
				IF string then assume that string refers to the location of a fasta file containing all reference sequences
			paired_seqs (boolean): If true then treat input files as R1/R2 FASTQ files
			sam_file_name (string): Name of the SAM file to be generated.

				..note::

				    The folder path should NOT be defined in this parameter. It should be defined in "working_directory" parameter

			bowtie_ref_name (string, default None): Name to refer to the reference index file generated by bowtie-build command. If None the filename will default to timestamp when function is called.
			working_directory (string, default None): Output path location to save the SAM file name. If None then default folder location will be the same as parent folder of input seq file
			include_phix (boolean, default True): If true then also include a search for phix in the input files
			phix_filter (boolean, default False): If true then after alignment, remove any sequences that show hits to phix control
			threads (int, default 2): Run bowtie using this many threads
			options (list of tuples): user can pass in any parameter/value pair recognized by bowtie program (i.e. [('--local'), ('--np', 10)])

		Returns:
			Location of the generated sam file
	"""

	# remove comment line to allow for "fake" bowtie (debugging)
	# return os.path.abspath(os.path.join(working_directory, sam_file_name))
	if isinstance(references, str):
		# this is a horrible hack to allow refernces to be passed as a list or a link to a fasta file...consider cleaning up in the future
		barcodes = [[r.description, str(r.seq)] for r in SeqIO.parse(references, 'fasta')]
		references = barcodes

	output_ref_dir = working_directory
	if working_directory is None:
		# make the default working directory equal to input fastq file 1
		working_directory = os.path.dirname(fastq_files[0])

	if include_phix:
		# also include the phix sequence into bowtie
		phix_fasta = os.path.join(current_dir, "phix.fasta")
		with open(phix_fasta) as r:
			r.readline()
			seq = ''.join([l.strip() for l in r])
			references.append(['phix', seq])

	if bowtie_ref_name is None:
		# make a default bowtie reference name based on timestampe
		bowtie_ref_name = re.sub("[\:\-\ \.]", "", str(datetime.now()))

	bowtie_ref_name = os.path.join(working_directory, os.path.basename(bowtie_ref_name))
	sam_file_name = os.path.join(working_directory, os.path.basename(sam_file_name))
	# write reference sequences as a fasta file (...yes seems slightly circuituous...consider improving)
	fastaname = bowtie_ref_name + '.fasta'
	if output_ref_dir is not None:
		if not os.path.isdir(output_ref_dir):
			os.makedirs(output_ref_dir)
		fastaname = os.path.join(output_ref_dir, fastaname)

	with open(fastaname, 'w') as out:
		for b in references:
			out.write('>{0}\n{1}\n'.format(b[0], b[1]))

	# run bowtie-build commandd
	ref = build_reference(fastaname, bowtie_ref_name, output_ref_dir)

	# ### OLD CODE ####
	# command = '-x "{0}" -1 "{1}" -2 "{2}"'.format(ref, os.path.abspath(fastq_files[0]), os.path.abspath(fastq_files[1])) if paired_seqs else '-x "{0}" -U {1}'.format(ref, ','.join([os.path.abspath(f).replace(' ', '\ ') for f in fastq_files]))
	# command += ' -S "{0}"'.format(os.path.abspath(os.path.join(working_directory, sam_file_name)))
	# extra_commands = '--threads {0}'.format(str(threads)) if threads else ''

	# for o in options:
		# if isinstance(o, tuple):
		# 	extra_commands += ' {0} {1}'.format(o[0], str(o[1])) if o[1] != '' else ' {0}'.format(o[0])
		# else:
		# 	extra_commands += ' ' + o

	# execute_call = ' '.join([os.path.join(bowtie_path, "bowtie2"), extra_commands, command])
	# print(execute_call)
	# ### END OF OLD CODE ######

	# make it as a list of commands to use "shell=False", note, to use shell=false, executable location must be a single element in list
	# https://jimmyg.org/blog/2009/working-with-python-subprocess.html
	command_list = [os.path.join(bowtie_path, "bowtie2")]
	# add in user provided options

	if threads:
		command_list.extend(['--threads', threads])
	for o in options:
		if isinstance(o, tuple):
			command_list.extend([o[0], o[1]] if o[1] != '' else [o[0]])
		else:
			command_list.append(o)
	# add reference sequence
	command_list.extend(['-x', ref])
	# add input files (fastq/fasta/tab, etc)
	if paired_seqs is True:
		command_list.extend(['-1', os.path.abspath(fastq_files[0]), '-2', os.path.abspath(fastq_files[1])])
	else:
		for f in fastq_files:
			command_list.extend(['-U', os.path.abspath(f)])
	# add output SAME file name

	command_list.extend(['-S', os.path.abspath(sam_file_name)])
	command_list = [str(c) for c in command_list]

	# RUN subprocess
	print(' '.join(command_list))
	proc = Popen(command_list, shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	# for some reason, both stdout and stderr is being merged into err. maybe this is bowtie specific?
	message, err = proc.communicate()

	if proc.returncode > 0:
		print('The following error was returned: ')
		print(err)
		raise Exception('Something went wrong when running bowtie: ' + err)

	if not os.path.isfile(os.path.abspath(sam_file_name)):
		raise Exception('There was no error running the command, but the SAM file was not generated. Please look at parameters')

	print('bowtie successfully completed')
	print(err)
	return os.path.abspath(sam_file_name)


def remove_phix_sequences(fastq_files, result_prefix, threads=2, return_orignal_name=True, delete_sam=True, delete_original_files=False):
	options = [
		('--un-conc', result_prefix),
	]

	if delete_original_files:
		return_orignal_name = True

	working_directory = os.path.dirname(fastq_files[0])
	refpath = os.path.join(working_directory, 'phix.ref')
	empty_sam = 'sam_file' + re.sub("[\:\-\ \.]", "", str(datetime.now())) + '.sam'
	bowtie2(fastq_files, references=[], sam_file_name=empty_sam, paired_seqs=True, working_directory=working_directory, include_phix=True, bowtie_ref_name=refpath, threads=threads, options=options)
	if delete_sam:
		os.remove(os.path.join(working_directory, empty_sam))
	if return_orignal_name:
		for i, f in enumerate(fastq_files):
			if delete_original_files:
				os.remove(f)
			else:
				os.rename(f, f + '.before-phix-filter.fastq')
			if i == 0:
				os.rename(result_prefix + '.1', f)
			elif i == 1:
				os.rename(result_prefix + '.2', f)
		return_files = fastq_files
	else:
		return_files = [result_prefix + '.1', result_prefix + '.2']

	return return_files


if __name__ == "__main__":
	# refs = [[s.description, str(s.seq)] for s in SeqIO.parse(sys.argv[1], 'fasta')]
	options = [
		('--local', ''),
		('--no-sq'),
		('--very-sensitive-local'),
		('--n-ceil', 'L,0,100'),
		('--np', 0),
		('--rfg', '20,4'),
		('--rdg', '20,4'),
		('--un-conc', 'discordinate_reads.sam'),
		('--dovetail'),
		('--no-discordant'),
		('--no-mixed')
	]
	# bowtie2(['testme/small_r1.fastq', 'testme/small_r2.fastq'], refs, True, 'out.sam', sys.argv[1] + '.ref', options=options, threads=4)
	remove_phix_sequences(['testme/small_r1.fastq', 'testme/small_r2.fastq'], result_prefix='testme/stuff_goes_here')
