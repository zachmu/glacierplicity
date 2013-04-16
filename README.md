###############################################################################
# glacierplicity
###############################################################################
# Glacier and duplicity, together at last!
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
# This project was inspired by this blog article about using duplicity with 
# glacier storage:
#
# http://blog.epsilontik.de/?page_id=68
#
# The main thing it does (other than store each directory in its own bucket) is
# to make sure the .manifest files don't get rotated into glacier. It could be
# pretty much obsoleted if s3 made their lifecycle rules a bit more expressive.
