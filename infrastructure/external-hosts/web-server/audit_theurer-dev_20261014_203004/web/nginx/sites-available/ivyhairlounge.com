server {
    server_name ivyhairlounge.com www.ivyhairlounge.com;
    root /var/www/ivyhairlounge.com/html;

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
    ssl_certificate /etc/letsencrypt/live/ivyhairlounge.com-0001/fullchain.pem; # managed by Certbot
    ssl_certificate_key /etc/letsencrypt/live/ivyhairlounge.com-0001/privkey.pem;

 # managed by Certbot

}
server {
       listen 80;
       listen [::]:80;
       server_name _;
       return 301 https://$host$request_uri;
}
server {
    if ($host = www.ivyhairlounge.com) {
        return 301 https://$host$request_uri;
    } # managed by Certbot


    if ($host = ivyhairlounge.com) {
        return 301 https://$host$request_uri;
    } # managed by Certbot


    listen 80;
    listen [::]:80;
    server_name ivyhairlounge.com www.ivyhairlounge.com;
    return 404; # managed by Certbot




}