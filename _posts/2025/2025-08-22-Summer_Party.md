---
layout: post
published: true
title: Summer Party!
date: '2025-08-22'
external-url:
teaser: 2025/summer_group.jpg
categories:
- Events
---

The lab enjoyed beautiful summer weather with smoked brisket and riveting discussion on the definition of salad.

<div>
{% for image in site.static_files %}
    {% if image.path contains '2025-08-22-Summer_Party' %}
        <img src="{{ site.baseurl }}{{ image.path }}" alt="image" />
    {% endif %}
{% endfor %}
</div>
