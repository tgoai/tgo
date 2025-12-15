"""Add visitor timezone, language, ip_address, and geolocation fields.

Revision ID: 0011_visitor_locale_fields
Revises: 0010_queue_ai_disabled
Create Date: 2024-12-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0011_visitor_locale_fields'
down_revision: Union[str, None] = '0010_queue_ai_disabled'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add timezone field
    op.add_column(
        'api_visitors',
        sa.Column(
            'timezone',
            sa.String(50),
            nullable=True,
            comment="Visitor timezone (e.g., 'Asia/Shanghai', 'America/New_York')"
        )
    )
    
    # Add language field
    op.add_column(
        'api_visitors',
        sa.Column(
            'language',
            sa.String(10),
            nullable=True,
            comment="Visitor preferred language code (e.g., 'en', 'zh-CN')"
        )
    )
    
    # Add ip_address field
    op.add_column(
        'api_visitors',
        sa.Column(
            'ip_address',
            sa.String(45),
            nullable=True,
            comment="Visitor IP address (supports both IPv4 and IPv6)"
        )
    )
    
    # Add geolocation fields (derived from IP address)
    op.add_column(
        'api_visitors',
        sa.Column(
            'geo_country',
            sa.String(100),
            nullable=True,
            comment="Country name derived from IP address"
        )
    )
    
    op.add_column(
        'api_visitors',
        sa.Column(
            'geo_country_code',
            sa.String(2),
            nullable=True,
            comment="ISO 3166-1 alpha-2 country code (e.g., 'US', 'CN')"
        )
    )
    
    op.add_column(
        'api_visitors',
        sa.Column(
            'geo_region',
            sa.String(100),
            nullable=True,
            comment="Region/state/province name"
        )
    )
    
    op.add_column(
        'api_visitors',
        sa.Column(
            'geo_city',
            sa.String(100),
            nullable=True,
            comment="City name"
        )
    )
    
    op.add_column(
        'api_visitors',
        sa.Column(
            'geo_isp',
            sa.String(100),
            nullable=True,
            comment="Internet Service Provider (available with ip2region)"
        )
    )


def downgrade() -> None:
    op.drop_column('api_visitors', 'geo_isp')
    op.drop_column('api_visitors', 'geo_city')
    op.drop_column('api_visitors', 'geo_region')
    op.drop_column('api_visitors', 'geo_country_code')
    op.drop_column('api_visitors', 'geo_country')
    op.drop_column('api_visitors', 'ip_address')
    op.drop_column('api_visitors', 'language')
    op.drop_column('api_visitors', 'timezone')
