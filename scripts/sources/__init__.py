"""
Source registry. Order is dedup canonical PRIORITY (earlier = preferred survivor when the
same deposit appears in several sources). Curated/national sets rank above noisy MRDS.

Add a source by importing its module and appending it to SOURCES.
"""

from . import (au_mines, bc_minfile, minfac, mrds, nrcan_900a, porcu, pp1802,
               ree_global, sedznpb, sk_smdi, usgs_africa, vms)

# Ordered by canonical priority (most-trusted first). Append new sources here.
SOURCES = [
    nrcan_900a,
    au_mines,
    usgs_africa,
    minfac,
    porcu,
    ree_global,
    sedznpb,
    vms,
    pp1802,
    bc_minfile,
    sk_smdi,
    mrds,
]
