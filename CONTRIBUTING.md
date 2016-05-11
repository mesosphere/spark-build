# Setup repo
```
# Public fork of Apache Spark.  Used for public pull requests.
git remote add origin git@github.com:mesosphere/spark.git

# Private fork of Apache Spark.  Contains our private commits.
git remote add private git@github.com:mesosphere/spark-private.git

# Apache Spark
git remote add upstream git@github.com:apache/spark
```

# Create an upstream feature branch
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

# Create a private feature branch
```
# update private/private-master
git checkout private-master
git pull private private-master
git fetch upstream
git rebase upstream/master
# resolve any merge conflicts
git checkout -b private/private-master <feature-branch>
git push private <feature-branch>
# create PR against private/private-master
# internal review
```

# Release
```
# wait for apache/spark to tag a release (follow the developers' email list)
git fetch private --tags
git fetch upstream --tags
git checkout -b upstream/branch-<version> private-branch-<version>
# cherry-pick private commits from private/private-master
git cherry-pick upstream/master..private/private-master
git push private private-branch-<version>
# ensure build passes
git tag -a private-<version>
git push private --tags
# TC will build this tag and produce a universe package as an
# artifact.  Create a universe PR from this TC build artifact.
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
