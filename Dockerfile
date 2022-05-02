FROM php:7.3-apache

# Install required debian packages
RUN apt-get update -y \
 && apt-get install -y sudo man bc jq wget \
                       libfreetype6-dev libjpeg62-turbo-dev libpng-dev libzip-dev libpq-dev \
                       libicu-dev postgresql librabbitmq-dev libgmp-dev

# Build and configure python3
RUN apt-get install -y build-essential \
                       libssl-dev zlib1g-dev libncurses5-dev libncursesw5-dev libreadline-dev libsqlite3-dev \
                       libgdbm-dev libdb5.3-dev libbz2-dev libexpat1-dev liblzma-dev libffi-dev uuid-dev
RUN cd /tmp \
 && wget https://www.python.org/ftp/python/3.8.5/Python-3.8.5.tgz \
 && tar xzf Python-3.8.5.tgz \
 && cd Python-3.8.5 \
 && ./configure --prefix=/opt/fairdata/python3 --enable-optimizations; make altinstall \
 && cd /opt/fairdata/python3/bin \
 && ln -s python3.8 python3 \
 && ln -s python3.8 python \
 && ln -s pip3.8 pip3 \
 && ln -s pip3.8 pip \
 && ./pip install --upgrade pip \
 && ./pip install virtualenv 

RUN ln -s /opt/fairdata/python3/bin/python3.8 /usr/bin/python3 \
 && ln -s /opt/fairdata/python3/bin/python3.8 /usr/bin/python \
 && ln -s /opt/fairdata/python3/bin/pip3.8 /usr/bin/pip3 \
 && ln -s /opt/fairdata/python3/bin/pip3.8 /usr/bin/pip

# Install php extensions
RUN docker-php-ext-configure gd --with-freetype-dir=DIR \
 && docker-php-ext-configure bcmath \
 && docker-php-ext-configure zip \
 && docker-php-ext-configure pgsql \
 && docker-php-ext-configure pdo_pgsql \
 && docker-php-ext-configure intl \
 && docker-php-ext-configure json \
 && docker-php-ext-configure mbstring \
 && docker-php-ext-install -j$(nproc) gd \
                                      zip \
                                      pcntl \
                                      pgsql \
                                      pdo_pgsql \
                                      intl \
                                      json \
                                      mbstring \
                                      bcmath \
                                      gmp \
 && pecl install redis-5.1.1 \
 && pecl install amqp \
 && docker-php-ext-enable amqp redis

# Enable required apache modules
RUN ln -s /etc/apache2/mods-available/ssl.conf /etc/apache2/mods-enabled/ssl.conf \
 && ln -s /etc/apache2/mods-available/ssl.load /etc/apache2/mods-enabled/ssl.load \
 && ln -s /etc/apache2/mods-available/socache_shmcb.load /etc/apache2/mods-enabled/socache_shmcb.load \
 && ln -s /etc/apache2/mods-available/proxy.load /etc/apache2/mods-enabled/proxy.load \
 && ln -s /etc/apache2/mods-available/rewrite.load /etc/apache2/mods-enabled/rewrite.load \
 && ln -s /etc/apache2/mods-available/headers.load /etc/apache2/mods-enabled/headers.load

# Copy PHP configuration files
COPY templates/php.ini $PHP_INI_DIR/php.ini
COPY templates/10-opcache.ini $PHP_INI_DIR/conf.d/10-opcache.ini
RUN chmod go+rwX $PHP_INI_DIR/php.ini $PHP_INI_DIR/conf.d/10-opcache.ini

# Initialize directories
RUN mkdir -p /mnt/storage_vol01/ida \
 && mkdir -p /mnt/storage_vol01/ida/control \
 && mkdir -p /mnt/storage_vol01/ida_replication \
 && mkdir -p /mnt/storage_vol01/ida_trash \
 && mkdir -p /mnt/storage_vol01/log 
RUN chown -R www-data:www-data /mnt/storage_vol01

# Install some useful utilities
RUN apt-get install -y git vim zsh
