def append_tag(tag, bucket=[]):
    """Return tags accumulated for one call."""
    bucket.append(tag)
    return bucket


def render_tags(tags):
    return ", ".join(tags)
