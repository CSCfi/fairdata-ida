FROM php:8.0-apache

# Install required and useful packages
RUN apt update -y
RUN apt install -y sudo man bc jq wget git vim zsh zip
RUN apt install -y libfreetype6-dev libjpeg62-turbo-dev libpng-dev libzip-dev libicu-dev librabbitmq-dev libgmp-dev
RUN apt install -y postgresql libpq-dev 
RUN apt install -y libzip-dev libpng-dev libjpeg-dev libwebp-dev libavif-dev libldap2-dev
RUN apt install -y libssl-dev libreadline-dev libbz2-dev libcurl4-openssl-dev libffi-dev libgmp-dev
RUN apt install -y libc-client-dev libkrb5-dev libpspell-dev zip zlib1g-dev libonig-dev
RUN apt install -y --no-install-recommends locales locales-all 

# Build and configure python3
RUN apt-get install -y build-essential \
                       libssl-dev zlib1g-dev libncurses5-dev libncursesw5-dev libreadline-dev libsqlite3-dev \
                       libgdbm-dev libdb5.3-dev libbz2-dev libexpat1-dev liblzma-dev libffi-dev uuid-dev
RUN cd /tmp \
 && wget "https://www.python.org/ftp/python/3.8.14/Python-3.8.14.tgz" \
 && tar xzf Python-3.8.14.tgz
RUN cd /tmp/Python-3.8.14 \
 && ./configure --prefix=/opt/fairdata/python3 --enable-optimizations; make altinstall \
 && cd /opt/fairdata/python3/bin \
 && ln -s python3.8 python3 \
 && ln -s python3.8 python \
 && ln -s pip3.8 pip3 \
 && ./pip3 install --upgrade pip \
 && ./pip3 install virtualenv 

# Install php extensions
RUN docker-php-ext-configure gd --with-freetype=DIR
RUN docker-php-ext-configure bcmath
RUN docker-php-ext-configure zip
RUN docker-php-ext-configure pgsql
RUN docker-php-ext-configure pdo_pgsql
RUN docker-php-ext-configure intl
RUN docker-php-ext-configure mbstring
RUN docker-php-ext-install -j$(nproc) gd
RUN docker-php-ext-install -j$(nproc) bcmath
RUN docker-php-ext-install -j$(nproc) zip
RUN docker-php-ext-install -j$(nproc) pgsql
RUN docker-php-ext-install -j$(nproc) pdo_pgsql
RUN docker-php-ext-install -j$(nproc) pcntl
RUN docker-php-ext-install -j$(nproc) intl
RUN docker-php-ext-install -j$(nproc) mbstring
RUN docker-php-ext-install -j$(nproc) gmp
RUN docker-php-ext-install -j$(nproc) sockets
RUN pecl install redis-5.3.7
RUN pecl install amqp
RUN docker-php-ext-enable amqp redis

# Enable required apache modules
RUN ln -s /etc/apache2/mods-available/ssl.conf /etc/apache2/mods-enabled/ssl.conf
RUN ln -s /etc/apache2/mods-available/ssl.load /etc/apache2/mods-enabled/ssl.load
RUN ln -s /etc/apache2/mods-available/socache_shmcb.load /etc/apache2/mods-enabled/socache_shmcb.load
RUN ln -s /etc/apache2/mods-available/proxy.load /etc/apache2/mods-enabled/proxy.load
RUN ln -s /etc/apache2/mods-available/rewrite.load /etc/apache2/mods-enabled/rewrite.load
RUN ln -s /etc/apache2/mods-available/headers.load /etc/apache2/mods-enabled/headers.load

# Copy PHP configuration files
COPY templates/php.ini $PHP_INI_DIR/php.ini
COPY templates/10-opcache.ini $PHP_INI_DIR/conf.d/10-opcache.ini
RUN chmod go+rwX $PHP_INI_DIR/php.ini $PHP_INI_DIR/conf.d/10-opcache.ini

# Initialize directories and simulated mount sentinel files
RUN mkdir -p /mnt/storage_vol01/log \
 && mkdir -p /mnt/storage_vol01/ida \
 && mkdir -p /mnt/storage_vol01/ida/control \
 && mkdir -p /mnt/storage_vol01/ida_replication \
 && mkdir -p /mnt/storage_vol01/ida_trash \
 && mkdir -p /mnt/storage_vol02/ida \
 && mkdir -p /mnt/storage_vol03/ida \
 && mkdir -p /mnt/storage_vol04/ida
RUN touch /mnt/storage_vol01/DO_NOT_DELETE_sentinel_file \
 && touch /mnt/storage_vol02/DO_NOT_DELETE_sentinel_file \
 && touch /mnt/storage_vol03/DO_NOT_DELETE_sentinel_file \
 && touch /mnt/storage_vol04/DO_NOT_DELETE_sentinel_file \
 && touch /mnt/storage_vol01/ida_replication/DO_NOT_DELETE_sentinel_file
RUN chown -R www-data:www-data /mnt/storage_vol01 \
 && chown -R www-data:www-data /mnt/storage_vol02 \
 && chown -R www-data:www-data /mnt/storage_vol03 \
 && chown -R www-data:www-data /mnt/storage_vol04 \
 && chmod -R g+rwX,o+rX-w /mnt/storage_vol01 \
 && chmod -R g+rwX,o+rX-w /mnt/storage_vol02 \
 && chmod -R g+rwX,o+rX-w /mnt/storage_vol03 \
 && chmod -R g+rwX,o+rX-w /mnt/storage_vol04

# Initialize default locale
RUN echo "LANGUAGE=en_US.UTF-8" > /etc/default/locale \
 && echo "LC_ALL=en_US.UTF-8" >> /etc/default/locale \
 && echo "LANG=en_US.UTF-8" >> /etc/default/locale \
 && echo "LC_CTYPE=en_US.UTF-8" >> /etc/default/locale

# Initialize statdb user account 
RUN adduser --disabled-password --gecos "" repputes
