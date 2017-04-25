---
layout: post
status: publish
title: Pumpkin carving!
date: '2016-10-21'
external-url:
teaser: 2016/Pumpkin_Carving.jpg
categories:
- Events
---

The lab has a nice team building exercise and moves away from science to show our art skills. We also said goodbye to Haley who will be moving on to another rotation. Adam's carving of the horse was voted best pumpkin of the night!

<div>
{% for image in site.static_files %}
    {% if image.path contains '2016-10-21-Pumpkin_Carving' %}
        <img src="{{ site.baseurl }}{{ image.path }}" alt="image" />
    {% endif %}
{% endfor %}
</div>
