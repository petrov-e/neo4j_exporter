FROM python:3.7.3-alpine3.9 as prod

RUN mkdir /app/
WORKDIR /app/

COPY ./src/requirements.txt /app/requirements.txt

RUN pip install --upgrade pip
RUN pip install -r /app/requirements.txt

COPY ./src/ /app/

ENV FLASK_APP=app.py
ENV FLASK_DEBUG=1
ENV PYTHONUNBUFFERED=1
CMD [ "python3", "-m" , "flask", "run", "--host=0.0.0.0"]
