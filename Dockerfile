FROM python:3.14 AS builder

WORKDIR /app

COPY requirements.txt .

RUN pip install -r requirements.txt

FROM python:3.14-slim

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.14/site-packages/ /usr/local/lib/python3.14/site-packages/

COPY . .

RUN python manage.py migrate

CMD ["python", "manage.py", "runserver", "0.0.0.0:8001"]