#!/bin/sh
#pkill csdaemon
#nohup /opt/cs/csdaemon.sh &

docker stop csPlugin1
docker rm csPlugin1

cd /opt/cs/java
rm comtest*.jar*
wget https://svn.cc.jyu.fi/srv/svn/comtest/proto/vesa/trunk/comtest.jar
wget https://svn.cc.jyu.fi/srv/svn/comtest/proto/vesa/trunk/comtestcpp.jar

rm Graphics.jar*
wget https://svn.cc.jyu.fi/srv/svn/ohj1/graphics/trunk/Graphics.jar
rm Ali*.jar
wget https://svn.cc.jyu.fi/srv/svn/ohj2/Ali/trunk/Ali.jar

# Copy Jypeli dll's to temp directory
mkdir /tmp/uhome
mkdir /tmp/uhome/cs
sudo cp /opt/cs/jypeli/* /tmp/uhome/cs


docker run --name csPlugin1 -t -i -p 56001:5000 -v /opt/cs:/cs/:ro -v /opt/cs/images/cs:/csimages/ -v /tmp/uhome:/tmp/ -w /cs cs3 /bin/bash  
