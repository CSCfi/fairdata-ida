FROM almalinux:9

# Update OS and install required and useful packages
RUN dnf update -y
RUN dnf install -y sudo procps man bc jq wget git vim zsh zip rsync

# Install required development tools and libraries
RUN dnf groupinstall -y "Development Tools"
RUN dnf install -y gcc curl-devel expat-devel gettext-devel openssl-devel zlib-devel perl-ExtUtils-MakeMaker asciidoc xmlto libffi-devel
RUN wget https://raw.githubusercontent.com/sobolevn/git-secret/master/utils/rpm/git-secret.repo -O /etc/yum.repos.d/git-secret-rpm.repo
RUN dnf install -y git-secret

# Install PostgreSQL (used by IDA)
RUN dnf install -y postgresql libpq-devel

# Install SQLite (used by download service)
RUN dnf install -y sqlite sqlite-devel

# Install PHP8.0
RUN dnf install https://dl.fedoraproject.org/pub/epel/epel-release-latest-9.noarch.rpm -y
RUN dnf install https://rpms.remirepo.net/enterprise/remi-release-9.rpm -y
RUN dnf module reset php -y
RUN dnf module install php:remi-8.0 -y

# Install PHP extensions
RUN dnf install -y php-amqp php-apcu php-bcmath php-cli php-common php-curl php-devel php-dom php-fpm php-gd \
                   php-imagick php-imap php-intl php-json php-ldap php-mbstring php-mcrypt php-memcache php-memcached \
                   php-mysqlnd php-opcache php-pdo php-pdo_pgsql php-pear php-pecl-apcu php-pecl-igbinary php-pecl-mcrypt \
                   php-pecl-msgpack php-pecl-redis php-pecl-zip php-pgsql php-posix php-process php-readline php-redis \
                   php-soap php-sockets php-xml php-xmlrpc php-zip

# Copy PHP configuration files
COPY templates/php.ini /etc/php.ini
COPY templates/10-opcache.ini /etc/php.d/10-opcache.ini
RUN chmod go+rX /etc/php.ini /etc/php.d/10-opcache.ini

# Install Apache
RUN dnf install -y httpd
RUN dnf install -y mod_ssl mod_php
RUN dnf install -y mod_security mod_security_crs

# Build and install Python3
RUN cd /tmp \
 && wget "https://www.python.org/ftp/python/3.8.14/Python-3.8.14.tgz" \
 && tar xzf Python-3.8.14.tgz
RUN cd /tmp/Python-3.8.14 \
 && ./configure --prefix=/opt/fairdata/python3 --enable-optimizations \
 && make altinstall \
 && cd /opt/fairdata/python3/bin \
 && ln -s python3.8 python3 \
 && ln -s python3.8 python \
 && ln -s pip3.8 pip3 \
 && ./pip3 install --upgrade pip \
 && ./pip3 install virtualenv 

# Initialize directories and simulated mount sentinel files
RUN mkdir -p /mnt/storage_vol01/log \
 && mkdir -p /mnt/storage_vol01/ida \
 && mkdir -p /mnt/storage_vol01/ida/control \
 && mkdir -p /mnt/storage_vol01/ida_trash \
 && mkdir -p /mnt/storage_vol02/ida \
 && mkdir -p /mnt/storage_vol03/ida \
 && mkdir -p /mnt/storage_vol04/ida \
 && mkdir -p /mnt/ida_upload_cache \
 && mkdir -p /mnt/tape_archive_cache 
RUN touch /mnt/storage_vol01/DO_NOT_DELETE_sentinel_file \
 && touch /mnt/storage_vol02/DO_NOT_DELETE_sentinel_file \
 && touch /mnt/storage_vol03/DO_NOT_DELETE_sentinel_file \
 && touch /mnt/storage_vol04/DO_NOT_DELETE_sentinel_file \
 && touch /mnt/ida_upload_cache/DO_NOT_DELETE_sentinel_file \
 && touch /mnt/tape_archive_cache/DO_NOT_DELETE_sentinel_file
RUN chown -R apache:apache /mnt/storage_vol01 \
 && chown -R apache:apache /mnt/storage_vol02 \
 && chown -R apache:apache /mnt/storage_vol03 \
 && chown -R apache:apache /mnt/storage_vol04 \
 && chown -R apache:apache /mnt/ida_upload_cache \
 && chown -R apache:apache /mnt/tape_archive_cache \
 && chmod -R g+rwX,o+rX-w /mnt/storage_vol01 \
 && chmod -R g+rwX,o+rX-w /mnt/storage_vol02 \
 && chmod -R g+rwX,o+rX-w /mnt/storage_vol03 \
 && chmod -R g+rwX,o+rX-w /mnt/storage_vol04 \
 && chmod -R g+rwX,o+rX-w /mnt/ida_upload_cache \
 && chmod -R g+rwX,o+rX-w /mnt/tape_archive_cache 

# Initialize statdb user account 
RUN adduser repputes

CMD /bin/bash -c 'sleep infinity' # required to keep the container running in docker swarm
