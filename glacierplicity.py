#!/ffp/bin/python
#
# Copyright 2013 Zach Musgrave, zach.musgrave@gmail.com
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Duplicity and glacier, together at last!
# http://duplicity.nongnu.org/duplicity.1.html
# http://aws.amazon.com/glacier/
#
# Glacierplicity uses duplicity's s3 backend to leverage its incremental backup 
# at glacier's much more affordable prices. It has two quirks that you should be
# aware of:
# 1) It creates a separate s3 bucket for each directory in the tree to be backed 
#    up. If you have enough storage volume to care about getting glacier prices 
#    (and you're on a standard US cable modem), you really don't want any 
#    individual archive getting much bigger than a few dozen gigs or they become 
#    very unwieldy.
# 2) Each bucket is named semi-randomly using the md5 sum of the backed-up path.
#    Bucket names can't be longer than 60 characters or so, which makes naming 
#    them directly after the path problematic. The path of the archive is also 
#    assigned to the bucket as a tag. It's easy to restore an individual 
#    directory, but will take some work to recreate all subdirectories as well.
#   
# This script was inspired by this blog article about using duplicity with 
# glacier storage:
#
# http://blog.epsilontik.de/?page_id=68
#
# The main thing it does (other than store each directory in its own bucket) is
# to make sure the .manifest files don't get rotated into glacier. It could be
# pretty much obsoleted if s3 made their lifecycle rules a bit more expressive.

from boto.s3.connection import S3Connection
from glob import glob
import os
import os.path
import string
import re
import pipes
import md5
import time
from boto.s3.lifecycle import Lifecycle, Transition, Rule
from boto.s3.tagging import Tag, Tags, TagSet
import sys

backup_dirs = ['/back/me/up']
ignore_directories = ['/ignore/this']
AWS_ACCESS_KEY_ID = "ACCESS"
AWS_SECRET_KEY = "SECRET"
PASSPHRASE = "GPG_PASSPHRASE"
s3_bucket_prefix = "your-name-here-backup-"
archive_dir = '/local/path/to/permanent/archive/dir'
duplicity = "duplicity --num-retries 5 --tempdir /ffp/tmp --no-encryption -v8" 
log_cmd = " >> /ffp/log/backup.log 2>&1"

def main():

	s3 = S3Connection(AWS_ACCESS_KEY_ID, AWS_SECRET_KEY)
	
	# we need to set up our environment for duplicity
	os.environ['AWS_ACCESS_KEY_ID'] = AWS_ACCESS_KEY_ID
	os.environ['AWS_SECRET_ACCESS_KEY'] = AWS_SECRET_KEY
	os.environ['PASSPHRASE'] = PASSPHRASE

	if '--restore' in sys.argv:
		restore(s3)
	else:
		backup(s3)

# Restores the current working directory from s3.
# This only works if the bucket contents have already 
# been restored from glacier into s3
def restore(s3):
	bucket_name = get_bucket_name(cwd)
	bucket = setup_bucket(s3, cwd, bucket_name)

	cwd = os.getcwd()
	cmd = duplicity + " s3+http://" + bucket_name + " " + cwd + "-duplicity-restore"
	print cmd
	if os.system(cmd):
		raise Exception
	
	cleanup_bucket(s3, bucket)

# Backs up all the directories specified at the top of the script, 
# as well as their subdirectories
def backup(s3):
	for dir in backup_dirs:
		for dirname, dirnames, filenames in os.walk(dir):
			try:
				if dirname in ignore_directories:
					dirnames = []
				else:
					backup_dir(dirname, dirnames, filenames, s3)
			except:
				print "Unexpected error, skipping " + dirname 

# Backs up the directory given to s3
def backup_dir(dirname, dirnames, filenames, s3):
	if not filenames:
		return

	bucket_name = get_bucket_name(dirname)
	
	# each bucket has its own archive directory. this directory isn't 
	# necessary, but makes incremental backups much faster
	bucket_archive_dir = archive_dir + bucket_name
	if not os.path.exists(bucket_archive_dir):
		os.mkdir(bucket_archive_dir)

	cmd = duplicity
	cmd += " --archive-dir " + bucket_archive_dir
	# tell duplicity not to recurse on any directories
	for dir in dirnames:
		cmd += " --exclude " + pipes.quote(os.path.join(dirname, dir))
	cmd += " " + pipes.quote(dirname)

	bucket = setup_bucket(s3, dirname, bucket_name)

	bucket_address = "s3+http://" + bucket_name
	cmd += " " + bucket_address
	cmd += log_cmd
	print cmd
	if os.system(cmd):
		raise Exception

	cleanup_bucket(s3, bucket)
 
# Gets a unique-ish (and consistent) bucket name from the directory path given
def get_bucket_name(dirname):
	m = md5.new()
	m.update(dirname)
	return s3_bucket_prefix + m.hexdigest()

# Ensures the given bucket exists and prepares it for a duplicity run
def setup_bucket(s3, dirname, bucket_name):
	if not s3.lookup(bucket_name):
		s3.create_bucket(bucket_name)
		time.sleep(5)
	bucket = s3.get_bucket(bucket_name)
	
	# tag this bucket with the directory so we know what it 
	# is when we retrieve it after the terrible fire or burglary
	tags = Tags()
	tagset = TagSet()
	tagset.add_tag('path', dirname)
	tags.add_tag_set(tagset)
	bucket.set_tags(tags)

	# turn off any lifecycle rotations while we are in the middle of a backup
	to_glacier = Transition(days=1, storage_class='GLACIER')
	rule = Rule('movetoglacier', 'duplicity', 'Disabled', transition=to_glacier)
	lifecycle = Lifecycle()
	lifecycle.append(rule)
	bucket.configure_lifecycle(lifecycle)

	# rename the manifest files from their glacier-safe versions
	keys = bucket.list(prefix = '_duplicity')
	for key in keys:
		key.copy(bucket_name, key.name.replace("_duplicity", "duplicity"))
		key.delete()

	return bucket

# Glacier-proofs the bucket	by renaming the .manifest files to not get moved 
# to glacier via our lifecycle rule
def cleanup_bucket(s3, bucket):
	# this isn't proof against eventual consistency, but it helps
	time.sleep(10)

	keys = bucket.list()
	
	# rename all the manifest and signature files so they don't get moved to glacier
	for key in keys:
		if not key.name.startswith("_") and \
		key.name.endswith(".manifest"):  # or key.name.endswith(".sigtar.gz")):
			key.copy(bucket.name, "_" + key.name)
			key.delete()

	# re-establish our lifecycle rules
	to_glacier = Transition(days=1, storage_class='GLACIER')
	rule = Rule('movetoglacier', 'duplicity', 'Enabled', transition=to_glacier)
	lifecycle = Lifecycle()
	lifecycle.append(rule)
	bucket.configure_lifecycle(lifecycle)

main()

