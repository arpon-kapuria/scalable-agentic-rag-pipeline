# OpenResty = Nginx + Lua runtime
FROM openresty/openresty:alpine

WORKDIR /etc/nginx

# Copy Nginx config
COPY nginx.conf /etc/nginx/nginx.conf

# Copy Lua rate limiting script
COPY rate_limit.lua /etc/nginx/lua/rate_limit.lua

EXPOSE 80

CMD ["openresty", "-g", "daemon off;"]