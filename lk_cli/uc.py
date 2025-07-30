#!/usr/bin/env python3
"""
UC - Remove tracking parameters from URLs
Usage: python uc.py <url>
"""

import click
import sys
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse


def get_version():
    """Get version for uc command."""
    return "0.9.1"


# Common tracking parameters to remove
TRACKING_PARAMS = {
    # Google Analytics and UTM parameters
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "utm_id",
    "utm_source_platform",
    "utm_creative_format",
    "utm_marketing_tactic",
    # Google Ads
    "gclid",
    "gclsrc",
    "dclid",
    # Facebook/Meta
    "fbclid",
    "fb_action_ids",
    "fb_action_types",
    "fb_source",
    # Microsoft/Bing
    "msclkid",
    # Twitter
    "twclid",
    # LinkedIn
    "li_fat_id",
    "lipi",
    # Pinterest
    "epik",
    # TikTok
    "ttclid",
    # Amazon
    "tag",
    "linkCode",
    "linkId",
    "ref_",
    "ref",
    "psc",
    # Other common tracking parameters
    "igshid",
    "gs_l",
    "_ga",
    "gws_rd",
    "ei",
    "ved",
    "uact",
    "sa",
    "source",
    "medium",
    "campaign",
    "content",
    "term",
    "affiliate_id",
    "aff_id",
    "partner_id",
    "referrer",
    "click_id",
    "clickid",
    "transaction_id",
    "tid",
    "mc_cid",
    "mc_eid",  # Mailchimp
    "vero_conv",
    "vero_id",  # Vero
    "_hsenc",
    "_hsmi",
    "hsCtaTracking",  # HubSpot
    "icid",  # IBM
    # Email/Newsletter tracking parameters
    "hid",
    "did",
    "lctg",
    "lr_input",  # Common email tracking
    "newsletter_id",
    "email_id",
    "subscriber_id",
    "list_id",
    "delivery_id",
    "message_id",
    "campaign_id",
    "send_id",
    "recipient_id",
    "hash_id",
    "tracking_id",
    "unique_id",
    "email_hash",
    "subscriber_hash",
    "delivery_hash",
    "open_id",
    "link_id",
    "click_hash",
    "track_id",
    "eid",
    "rid",
    "sid",
    "cid",
    "mid",
    "lid",  # Short form IDs
    "token",
    "signature",
    "auth_token",
    "verification",
    "unsubscribe_token",
    "opt_out",
    "preferences_token",
    # Additional newsletter/media tracking
    "newsletter",
    "bulletin",
    "digest",
    "alert",
    "notification",
    "update",
    "promo",
    "offer",
    "social_ref",
    "email_ref",
    "newsletter_ref",
    "source_code",
    "promo_code",
    "offer_code",
    "tracking_code",
    "reference_code",
    "campaign_code",
}


def clean_url(url):
    """
    Remove tracking parameters from a URL.

    Args:
        url (str): The URL to clean

    Returns:
        str: The cleaned URL without tracking parameters
    """
    try:
        # Parse the URL
        parsed = urlparse(url)

        # Parse query parameters
        query_params = parse_qs(parsed.query, keep_blank_values=True)

        # Remove tracking parameters (case-insensitive)
        cleaned_params = {}
        for key, value in query_params.items():
            # Check if parameter is a tracking parameter (case-insensitive)
            if key.lower() not in {param.lower() for param in TRACKING_PARAMS}:
                cleaned_params[key] = value

        # Rebuild query string
        cleaned_query = urlencode(cleaned_params, doseq=True)

        # Rebuild URL
        cleaned_url = urlunparse(
            (
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                parsed.params,
                cleaned_query,
                parsed.fragment,
            )
        )

        return cleaned_url

    except Exception as e:
        print(f"Error parsing URL: {e}", file=sys.stderr)
        return url


@click.command()
@click.version_option(get_version(), prog_name="uc")
@click.argument("url", required=False)
@click.option(
    "-v", "--verbose", is_flag=True, help="Show both original and cleaned URLs"
)
@click.option(
    "--list-params",
    is_flag=True,
    help="List all tracking parameters that will be removed",
)
def uc(url, verbose, list_params):
    """
    Remove tracking parameters from URLs.

    Examples:
      uc "https://example.com/?utm_source=google&utm_medium=cpc&id=123"
      uc "https://amazon.com/product?ref=sr_1_1&tag=affiliate123&psc=1"

    Common tracking parameters removed:
      UTM parameters (utm_source, utm_medium, etc.)
      Google Ads (gclid, gclsrc, dclid)
      Facebook (fbclid, fb_action_ids, etc.)
      Amazon (tag, ref, psc, etc.)
      And many more...
    """
    # List tracking parameters if requested
    if list_params:
        click.echo("Tracking parameters that will be removed:")
        for param in sorted(TRACKING_PARAMS):
            click.echo(f"  {param}")
        return

    if not url:
        click.echo(
            "Error: URL argument is required unless using --list-params", err=True
        )
        return

    # Clean the URL
    original_url = url
    cleaned_url = clean_url(original_url)

    if verbose:
        click.echo(f"Original: {original_url}")
        click.echo(f"Cleaned:  {cleaned_url}")
        if original_url == cleaned_url:
            click.echo("No tracking parameters found.")
    else:
        click.echo(cleaned_url)


if __name__ == "__main__":
    uc()
