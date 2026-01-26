import logging

import ingest


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ingest.purge_qdrant_chunks()


if __name__ == "__main__":
    main()
