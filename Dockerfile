# neden slim-bullseye? çünkü daha küçük ve güvenli bir imaj, debian 11 tabanlı
FROM python:3.11-slim-bullseye 

# python çıktısını hemen görmek için
ENV PYTHONUNBUFFERED=1 
# .pyc dosyaları oluşturmasın diye
ENV PYTHONDONTWRITEBYTECODE=1

# çalışma dizinini ayarla /app olarak
WORKDIR /app/app

# sistem bağımlılıklarını yükle postgre ve diğer paketler için
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# base.txt dosyasını kopyala ve bağımlılıkları yükle
COPY requirements/base.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# proje dosyalarını kopyala
COPY . /app/

# varsayılan komut: python sürümünü gösteri, ilerde python manage.py runserver olcak 
#CMD ["python", "--version"]
CMD sh -c "python /app/app/manage.py migrate && daphne -b 0.0.0.0 -p ${PORT:-8000} config.asgi:application"