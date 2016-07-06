FROM ubuntu:16.04
RUN apt-get update
RUN apt-get install -y ogmrip python3-venv

WORKDIR /app
RUN pyvenv env
RUN env/bin/pip install pycountry requests
COPY tomoji.py ./

ENTRYPOINT ["/app/env/bin/python3", "tomoji.py"]
CMD ["list"]
