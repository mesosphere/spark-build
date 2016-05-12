**WARNING:** that not all these instructions have been tested, especially the
specific git commands.  They are meant to give an idea of how each
process is carried out.

# Setup repo
```
# Public fork of Apache Spark.  Used for public pull requests.
git remote add origin git@github.com:mesosphere/spark.git

# Private fork of Apache Spark.  Contains our private commits.
git remote add private git@github.com:mesosphere/spark-private.git

# Apache Spark
git remote add upstream git@github.com:apache/spark
```

# Upstream PR

You'll create an upstream PR when you write code to be contributed
into Apache Spark.  This excludes private, proprietary features.

```
git pull upstream
git checkout -b upstream/master <feature-branch>
# update origin/master
git checkout master
git pull upstream
git push origin
# push feature branch
git push origin <feature-branch>
# create PR against origin/master
# internal review
# create PR against upstream/master
# external review
```

# Private PR

You'll create a private PR when you write private, proprietary code.

```
# update private/private-master:
git checkout private-master
git pull private private-master

# create feature branch
git checkout -b private/private-master <feature-branch>

# write feature

# review:
git push private <feature-branch>
# create PR against private/private-master
# internal review
# merge in github
```

# Release

A release of a DC/OS Spark package is two steps:

1. Release a Spark distribution
2. Release a DC/OS Spark package

## Dist Release

We cut a DC/OS Spark release in two scenarios:

1. Apache Spark cuts a release.
2. We need to make a bugfix release.

Follow the instruction for creating a tag depending on which release
you're doing:

### Apache Spark tag

```
# Wait for apache/spark to tag a release (follow the developers' email
# list).  Let <version> be the release version.
# fetch remotes:
git fetch private --tags
git fetch upstream --tags

# rebase private-master:
git checkout private/private-master
git rebase upstream/master
# resolve merge conflicts

# create release branch:
git checkout -b v<version> private-branch-<version>
git cherry-pick upstream/master..private/private-master
# resolve merge conflicts

# push:
git push private private-branch-<version>
# ensure build passes
git tag -a private-<version>
```

### Bugfix tag

In the case of a bugfix release, there is some commit(s) on
`private-master` that you wish to backport to an existing branch.

```
git checkout private-branch-<version>
git cherry-pick <commit>
# <bugfix> is a serial number starting at "1"
git tag -a private-<version>-<bugfix>
```

### Release

```
git push private --tags
# TC will build a distribution for <version>, and upload it to S3.
# Take the S3 URL and proceed to the "Package Release"
```

## Package Release

These instructions are for the `spark-build` repo (this repo).

```
git checkout master
# Update manifest.json with the latest `spark-uri`
git commit -a -m "Updated spark-uri to version <dist-version>"
# The <package-version> for the tag is the same as the previous
# <package-version>.  We only bump the <package-version> when the actual
# packaging has changed:
git tag -a <package-version>-<dist-version>

# push:
git push origin --tags
# Wait for "release package" build to complete.  The DC/OS package is
# published as an artifact of this build.  Take it and create a
# universe PR.
```

# Branches
## upstream
- `upstream/master` # upstream master
- `upstream/branch-<version>` # upstream version branch

## origin
- `origin/<feature>` # your upstream-able feature branch

## private
- `private/<feature>` # private feature branch
- `private/private-master` # all private commits on top of `upstream/master`
- `private/private-branch-<version>` # private commits on top of `upstream/branch-<version>`
