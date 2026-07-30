---
layout: post
published: true
title: Spring Fling!
date: '2022-04-29'
external-url:
teaser: 2022/pinata.jpg
categories:
- Events
---

The lab got together for some backyard fun with a piñata and nacho bar!

<div>
{% for image in site.static_files %}
    {% if image.path contains '2022-04-29-Spring_Fling' %}
        <img src="{{ site.baseurl }}{{ image.path }}" alt="image" />
    {% endif %}
{% endfor %}
</div>
