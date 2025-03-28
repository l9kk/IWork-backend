def format_currency(amount: float) -> str:
    """Format a currency amount into a human-readable string"""
    if amount >= 1_000_000_000:
        return f"${amount / 1_000_000_000:.2f} billion"
    elif amount >= 1_000_000:
        return f"${amount / 1_000_000:.2f} million"
    elif amount >= 1_000:
        return f"${amount / 1_000:.2f} thousand"
    else:
        return f"${amount:.2f}"


def format_large_number(number: float) -> str:
    """Format large numbers in a human-readable way"""
    if number >= 1_000_000_000:
        return f"{number / 1_000_000_000:.1f}B"
    elif number >= 1_000_000:
        return f"{number / 1_000_000:.1f}M"
    elif number >= 1_000:
        return f"{number / 1_000:.1f}K"
    else:
        return str(number)
