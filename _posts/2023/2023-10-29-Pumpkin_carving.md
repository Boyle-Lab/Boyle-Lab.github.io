---
layout: post
status: publish
title: The lab carves pumpkins!
date: '2023-10-29'
external-url:
teaser: 2023/carving.png
categories:
- Events
---

We continued our annual pumpkin-carving party tradition! We enjoyed the great weather while we created our masterpieces, and had some fun playing VR headset games later in the evening!

<div>
{% for image in site.static_files %}
    {% if image.path contains '2023-10-29-Pumpkin_carving' %}
        <img src="{{ site.baseurl }}{{ image.path }}" alt="image" />
    {% endif %}
{% endfor %}
</div>
