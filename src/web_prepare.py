#!/usr/bin/env python3
"""
Prepares what the web app would otherwise compute when first asked: the
voter-flow estimates and the figures of the analyses. web_api.py runs it in
the background at start; whatever is already stored on disk is only read.
"""

import logging

import web_analyses
import web_store

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(message)s")
    logger = logging.getLogger(__name__)
    logger.info("Voter-flow estimates ready: %s", web_store.precompute_comparisons())
    logger.info("Analyses ready: %s", web_analyses.precompute())
