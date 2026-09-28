server {
    listen 80;
    listen [::]:80;
    server_name theivyhairlounge.com www.theivyhairlounge.com;
    root /var/www/theivyhairlounge.com/html;

    index index.html index.htm index.php;

    location / {
        try_files $uri $uri/ =404;
    }

    location ~ \.php$ {
        include snippets/fastcgi-php.conf;
        fastcgi_pass unix:/var/run/php/php8.3-fpm.sock;
     }

    location ~ /\.ht {
        deny all;
    }

   listen 443 ssl;
   listen [::]:443 ssl;

   ssl_certificate /etc/letsencrypt/live/theivyhairlounge.com/fullchain.pem;
   ssl_certificate_key /etc/letsencrypt/live/theivyhairlounge.com/privkey.pem;

}
server {
       listen 80;
       listen [::]:80;
       server_name _;
       return 301 https://$host$request_uri;
}
