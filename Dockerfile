ARG BASE_IMAGE=nvcr.io/nvidia/cuquantum-appliance:25.11-x86_64
FROM ${BASE_IMAGE}

ENV PYTHONHASHSEED=10
ENV PYTHONPATH=/home/cuquantum/src/pydeps
ENV PATH=/home/cuquantum/src/bin:${PATH}

COPY src /home/cuquantum/src
WORKDIR /home/cuquantum

CMD ["bash", "-lc", "source /home/cuquantum/src/env.sh && bash"]
