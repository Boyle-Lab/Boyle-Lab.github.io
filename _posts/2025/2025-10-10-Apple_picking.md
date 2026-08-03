---
layout: post
published: true
title: The lab eats donuts!
date: '2025-10-10'
external-url:
teaser: 2025/group.jpg
categories:
- Events
---

We took a trip to Wasem Fruit Farm, where we ate delicious donuts, drank apple cider, and picked pumpkins!

<div>
{% for image in site.static_files %}
    {% if image.path contains '2025-10-10-Wasem_fruit' %}
        <img src="{{ site.baseurl }}{{ image.path }}" alt="image" />
    {% endif %}
{% endfor %}
</div>
