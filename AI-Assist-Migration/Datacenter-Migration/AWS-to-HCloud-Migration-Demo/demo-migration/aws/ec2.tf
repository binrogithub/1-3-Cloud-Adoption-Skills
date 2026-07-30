resource "aws_instance" "web" {
  ami                         = data.aws_ami.ubuntu_2204.id
  instance_type               = "m7i-flex.large"
  subnet_id                   = aws_subnet.public_1.id
  vpc_security_group_ids      = [aws_security_group.ec2.id]
  key_name                    = aws_key_pair.demo.key_name
  associate_public_ip_address = true
  user_data_replace_on_change = true

  user_data = <<-SCRIPT
              #!/bin/bash
              set -e

              apt update -y
              apt upgrade -y
              apt install -y apache2 \
                php php-mysql php-gd php-xml php-mbstring php-intl php-opcache \
                php-zip php-soap php-bcmath php-curl php-imagick wget tar mariadb-client

              a2enmod rewrite
              systemctl enable apache2
              systemctl start apache2

              wget -q -O /tmp/wordpress.tar.gz https://wordpress.org/latest.tar.gz
              tar -xzf /tmp/wordpress.tar.gz -C /tmp
              cp -a /tmp/wordpress/. /var/www/html/
              rm -rf /tmp/wordpress /tmp/wordpress.tar.gz
              rm -f /var/www/html/index.html

              cat > /var/www/html/wp-config.php <<'WPCONFIG'
              <?php
              define('DB_NAME',     'wordpress');
              define('DB_USER',     'admin');
              define('DB_PASSWORD', 'ChangeMe123!');
              define('DB_HOST',     '${aws_db_instance.main.address}');
              define('DB_CHARSET',  'utf8mb4');
              define('DB_COLLATE',  '');

              define('AUTH_KEY',         '${random_password.wp_auth_key.result}');
              define('SECURE_AUTH_KEY',  '${random_password.wp_secure_auth_key.result}');
              define('LOGGED_IN_KEY',    '${random_password.wp_logged_in_key.result}');
              define('NONCE_KEY',        '${random_password.wp_nonce_key.result}');
              define('AUTH_SALT',        '${random_password.wp_auth_salt.result}');
              define('SECURE_AUTH_SALT', '${random_password.wp_secure_auth_salt.result}');
              define('LOGGED_IN_SALT',   '${random_password.wp_logged_in_salt.result}');
              define('NONCE_SALT',       '${random_password.wp_nonce_salt.result}');

              $table_prefix = 'wp_';

              define('WP_DEBUG', false);

              if (!defined('ABSPATH')) {
                  define('ABSPATH', __DIR__ . '/');
              }

              require_once ABSPATH . 'wp-settings.php';
              WPCONFIG

              chown -R www-data:www-data /var/www/html/
              chmod -R 755 /var/www/html/
              mkdir -p /var/www/html/wp-content/uploads
              chown -R www-data:www-data /var/www/html/wp-content/uploads

              sed -i 's/AllowOverride None/AllowOverride All/g' /etc/apache2/apache2.conf

              for i in $(seq 1 30); do
                if mysqladmin ping -h ${aws_db_instance.main.address} -u admin -p'ChangeMe123!' --connect-timeout=5 2>/dev/null; then
                  break
                fi
                echo "Waiting for RDS... attempt $i/30"
                sleep 10
              done

              systemctl restart apache2
              SCRIPT

  tags = {
    Name = "demo-web"
  }

  depends_on = [aws_db_instance.main]
}
