"""Shared progress messages. Percentages measure work units, not elapsed time."""
import logging

LOG = logging.getLogger('po_pop')


def stage(percent, message):
    LOG.info('[Overall %5.1f%%] %s', percent, message)


def batch_progress(label, completed, total, interval=100):
    if completed == 1 or completed == total or completed % interval == 0:
        LOG.info('[%s %5.1f%%] %s/%s completed', label,
                 completed * 100 / total if total else 100, completed, total)
