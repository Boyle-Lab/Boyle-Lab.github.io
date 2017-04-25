---
layout: post
status: publish
title: The Boyle Lab takes a break at the lake!
date: '2016-08-20'
external-url:
teaser: 2016/LakeDay.jpg
categories:
- Events
---

The lab takes a break from work to enjoy a relaxing day at a lake near Greg's house. Thanks for hosting a great event, Greg!

<div>
{% for image in site.static_files %}
    {% if image.path contains '2016-08-20-Lab_Lake_Day' %}
        <img src="{{ site.baseurl }}{{ image.path }}" alt="image" />
    {% endif %}
{% endfor %}
</div>
