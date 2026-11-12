FROM gcc@sha256:056fa682471704249f619f65ccec87d671ad5f1b20878da54d60b0b863486621
# Toolchain provisioning is separate from network-disabled candidate execution.
# The resulting image ID, cmake version, and compiler version are recorded.
RUN apt-get update && apt-get install -y --no-install-recommends cmake strace \
    && rm -rf /var/lib/apt/lists/*
COPY . /opt/preflight/
ENV HOME=/nonexistent TMPDIR=/work
WORKDIR /work
USER 65534:65534
ENTRYPOINT ["python3", "-B", "/opt/preflight/inside.py"]
