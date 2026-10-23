# -*- coding: utf-8 -*-
"""Legacy PNG migration is disabled: it used src.unlink() and bypassed IDs.

It previously changed the user's OneDrive archive using hard-coded paths.
Use the separate, copy-only Tools Center converter for deliberate conversions.
This module is deliberately non-mutating even if directly executed.
"""

class UnsafeLegacyMigrationBlocked(RuntimeError):
    pass


def imwrite_unicode(*args, **kwargs):
    raise UnsafeLegacyMigrationBlocked("P0_MIGRATION_DISABLED_NO_OVERWRITE")


def convert_file(*args, **kwargs):
    raise UnsafeLegacyMigrationBlocked("P0_MIGRATION_DISABLED_NO_SOURCE_DELETE")


def migrate_to_png(*args, **kwargs):
    raise UnsafeLegacyMigrationBlocked(
        "P0_MIGRATION_DISABLED: eski migrasyon kaynaklari silebiliyordu. "
        "Profesyonel Araclar guvenli, kaynak-koruyan format donusturucuyu kullanin."
    )


if __name__ == "__main__":
    migrate_to_png()
