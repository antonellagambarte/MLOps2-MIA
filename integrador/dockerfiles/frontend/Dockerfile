FROM node:22-slim

WORKDIR /app

# Las dependencias primero: cambiar un .vue no reinstala nada.
COPY frontend/package.json frontend/package-lock.json /app/
RUN npm ci

COPY frontend/ /app/

EXPOSE 3000
CMD ["npm", "run", "dev"]
