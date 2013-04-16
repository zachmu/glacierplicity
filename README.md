###############################################################################
# glacierplicity
###############################################################################
# Glacier and duplicity, together at last!
# http://duplicity.nongnu.org/duplicity.1.html
# http://aws.amazon.com/glacier/

Glacierplicity uses duplicity's s3 backend to leverage its incremental backup at glacier's much more affordable prices. It's aimed at people who have hundreds of gigs of data to backup, and aren't willing to pay s3's prices. It has two quirks that you should be aware of:
1) Tries to keep the size of each archive (bucket) under control. Mainly it does this by putting any directory larger than some threshold (8GB by default) into its own, separate archive. This keeps the number of files in each archive reasonably small, since duplicity needs to list them when it runs. Having tens of thousands gets problematic.
2) Each bucket is named semi-randomly using the md5 sum of the backed-up path. Bucket names can't be longer than 60 characters or so, which makes naming them directly after the path problematic. The path of the archive is also assigned to the bucket as a tag. It's easy to restore an individual directory, but will take some work to recreate all subdirectories as well.
  
This project was inspired by this blog article about using duplicity with glacier storage:

http://blog.epsilontik.de/?page_id=68

The main thing it does (other than split things into multiple buckets) is to make sure the .manifest files don't get rotated into glacier. It could be pretty much obsoleted if s3 made their lifecycle rules a bit more expressive, or if duplicity takes on this behavior itself.

Known limitations: you only get 100 S3 buckets. If your archive is large enough (many TB), you could easily hit this limit.  At the very least, you'll need to dramatically increase the "large directory" threshold in the script, and even then some modifications will likely be necessary for it to work.