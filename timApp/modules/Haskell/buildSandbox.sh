#!/bin/bash
set -euo pipefail
IFS=$'\n\t'

# This is used by the container to rebuild the cabal sandbox if necessary

cd /Haskell
if [ ! -d ".cabal-sandbox/" ]; 
 then
  cabal sandbox init
  cabal update;
fi

gitGet () {
    if [ ! -d "$1" ]; 
     then
         git clone $2 $1 #http://yousource.it.jyu.fi/ties343-funktio-ohjelmointi/PluginConstructionKit.git
     else 
         (cd $1 && exec git fetch && exec git merge origin/master)
    fi
}
gitGet PluginConstructionKit git://yousource.it.jyu.fi/ties343-funktio-ohjelmointi/PluginConstructionKit.git
gitGet Choices git://yousource.it.jyu.fi/ties343-funktio-ohjelmointi/MultipleChoicePlugin.git

cabal install PluginConstructionKit/ Choices/
