---
layout: post
status: publish
title: Pumpkin Carving!
date: '2020-10-25'
external-url:
teaser: 2020/Pumpkin_Carving.jpg
categories:
- Events
---

The Boyle Lab celebrates new lab members and successful funding in the lab with a pumpkin carving competition! 

<div>
{% for image in site.static_files %}
    {% if image.path contains '2020-10-25-Pumpkin_Carving' %}
        <img src="{{ site.baseurl }}{{ image.path }}" alt="image" />
    {% endif %}
{% endfor %}
</div>
