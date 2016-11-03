#!/bin/bash
#
echo "------------------------------"
echo " Merging spark-build"
echo "------------------------------"

# Move to the top level of the repo
root="$(git rev-parse --show-toplevel)"
cd $root

# pull spark
git remote rm spark-build 
git remote add spark-build git@github.com:mesosphere/spark-build.git
git fetch spark-build > /dev/null 2>&1 

# checkout each file in the merge list from spark-build/ss/auto-merge-test 
while read p; do
  echo $p
  # checkout
  git checkout spark-build/ss/auto-merge-test $p
  # markdown files only
  if [ ${p: -3} == ".md" ]; then
  	# insert tag ( markdown files only )
    awk -v n=2 '/---/ { if (++count == n) sub(/---/, "---\n\n<!-- This source repo for this topic is https://github.com/mesosphere/spark-build -->\n"); } 1{print}' $p > tmp && mv tmp $p
  	# remove /docs/ from dcos links
	# awk '{gsub(/\/https:\/\/docs.mesosphere.com\/1.7\//,"/1.7/");}{print}' $p > tmp && mv tmp $p
	# awk '{gsub(/\/https:\/\/docs.mesosphere.com\/1.8\//,"/1.8/");}{print}' $p > tmp && mv tmp $p
	# awk '{gsub(/\/https:\/\/docs.mesosphere.com\/1.9\//,"/1.9/");}{print}' $p > tmp && mv tmp $p
  fi

cp docs/* 1.8/usage/service-guides/spark/
cp docs/* 1.9/usage/service-guides/spark/
rm -r docs/

done <scripts/spark-build-merge-list.txt

echo "------------------------------"
echo " spark-build merge complete"
echo "------------------------------"