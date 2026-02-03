FROM public.ecr.aws/lambda/python:3.11

COPY requirements.txt .

# Upgrade pip and install requirements
# - Force wheels only for numpy/pandas (prevents gcc builds)
# - Allow sdists for pure python packages like ta
RUN pip install --upgrade pip \
 && pip install --only-binary=numpy,pandas -r requirements.txt --target "${LAMBDA_TASK_ROOT}"

COPY market_predictor/ ${LAMBDA_TASK_ROOT}/

CMD ["lambda_handler.handler"]
