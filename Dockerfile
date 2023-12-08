FROM python:3.11

WORKDIR /app
COPY ./dummy.pdf /app/dummy.pdf
COPY ./main.py /app/main.py
COPY ./requirements.txt /app/requirements.txt
COPY ./test5.py /app/test5.py
COPY ./test4.py /app/test4.py
COPY ./Financial_statement_2023.pdf /app/Financial_statement_2023.pdf

RUN apt-get upgrade
RUN apt-get install libmagickwand-dev
RUN apt-get update && apt-get install -y ghostscript
RUN apt install tesseract-ocr -y 

RUN apt-get update -y
RUN apt-get install vim -y
COPY ./policy.xml /etc/ImageMagick-6/policy.xml

RUN pip install --upgrade pip
RUN pip install -r requirements.txt
RUN pip install gunicorn



