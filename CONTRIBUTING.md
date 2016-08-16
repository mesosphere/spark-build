**WARNING:** not all these instructions have been tested, especially
the specific git commands, and they shouldn't be followed mindlessly.
They are meant to give an idea of how each process is carried out.
You should first understand what the hell you're doing.

# Setup repo
```
# Public fork of Apache Spark.  Used for public pull requests.
git remote add origin git@github.com:mesosphere/spark.git
git fetch origin

# Private fork of Apache Spark.  Contains our private commits.
git remote add private git@github.com:mesosphere/spark-private.git
git fetch private

# Apache Spark
git remote add upstream git@github.com:apache/spark
git fetch upstream
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
git checkout private-master
git rebase master

# create release branch:
git checkout -b private-branch-<version> v<version>

# cherry-pick custom commits:
git cherry-pick upstream/master..private/private-master

# push:
git push private private-branch-<version>
# ensure build passes
git tag -a private-<version>
```

### Bugfix tag

In the case of a bugfix release, there is some commit(s) on
`private-master` that you wish to backport to an existing branch.

```
# Checkout latest version
git checkout -b private-branch-<version> private/private-branch-<version>
# Cherry pick the commit noted above
git cherry-pick <commit>
# <bugfix> is a serial number starting at "1" for example: private-1.6.1-2
git tag -a private-<version>-<bugfix>
```

### Release

```
git push private --tags
# TC will build a distribution for <version>, and upload it to S3.
# 1. OSS/Spark/package private parameterize with TEST_BRANCH refs/head/scala-2.10
# 2. Maybe add DCOS_URL environment variable when CCM is broken
# 3. OSS/Spark/release dist (maybe manually select dependency of "private dist" build)  Should be very fast.
# 4. Take the S3 URL from the build log and proceed to the "Package Release"
```

## Package Release

These instructions are for the `spark-build` repo (this repo).

```
git checkout master
# Update manifest.sh with the latest `SPARK_DIST_URI` with the S3 URL acquired above
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
# TeamCity Manual Steps
# 1. OSS/Spark/release package parameterize branch with refs/head/scale-2.10
# 2. Get build artifacts from successful build and make a PR against the Universe
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
