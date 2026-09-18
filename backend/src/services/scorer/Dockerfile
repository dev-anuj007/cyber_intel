# Scorer Microservice AWS Lambda Container Image
FROM public.ecr.aws/lambda/python:3.11

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR ${LAMBDA_TASK_ROOT}

# Install dependencies
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY backend/src/ ./src/

CMD ["src.services.scorer.lambda_handler.handler"]
