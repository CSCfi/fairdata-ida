FROM php:7.3-apache

# Install required debian packages
RUN apt-get update -y \
 && apt-get install -y man bc jq \
   libfreetype6-dev libjpeg62-turbo-dev libpng-dev libzip-dev libpq-dev libicu-dev postgresql librabbitmq-dev libgmp-dev

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

# Install python3
RUN apt-get install -y sudo python3 python3-venv python3-pip \
 && ln -s /usr/bin/python3 /usr/bin/python

# Initialize directories
RUN mkdir -p /mnt/storage_vol01/ida \
 && mkdir -p /mnt/storage_vol01/ida/control \
 && mkdir -p /mnt/storage_vol01/ida_replication \
 && mkdir -p /mnt/storage_vol01/ida_trash \
 && mkdir -p /mnt/storage_vol01/log 
RUN chown -R www-data:www-data /mnt/storage_vol01

# Install some useful utilities
RUN apt-get install -y git vim zsh
