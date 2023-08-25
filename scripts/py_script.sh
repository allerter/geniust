#!/bin/bash

# install git and clone repo
sudo apt-get update
sudo apt-get install git
cd ~
git clone https://github.com/allerter/geniust.git

# install python and its requirements
PYTHON_VERSION=$(cat geniust/runtime.txt | sed 's/-//')
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt-get update
sudo apt-get -y install $PYTHON_VERSION python3-pip python3-dev libpq-dev
pip install virtualenv
virtualenv -p 3.8 geniust_env
source geniust_env/bin/activate
cd geniust
pip install -r requirements.txt
pip install -e .

# get ssl certificates
apt install snapd
sudo snap install --classic certbot
sudo ln -s /snap/bin/certbot /usr/bin/certbot
sudo certbot certonly --standalone
cp /etc/letsencrypt/live/*name*/fullchain.pem ~/geniust/
cp /etc/letsencrypt/live/*name*/privkey.pem ~/geniust/