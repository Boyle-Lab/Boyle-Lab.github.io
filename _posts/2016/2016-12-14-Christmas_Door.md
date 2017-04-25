---
layout: post
status: publish
title: Boyle Lab wins door decorating contest!
date: '2016-12-14'
external-url:
teaser: 2016/Christmas_Door.jpg
categories:
- Fun
---

The Boyle and Parker labs win the annual DCM&B door decorating contest for the 'Most Creative Door'!

<div>
{% for image in site.static_files %}
    {% if image.path contains '2016-12-14-Christmas_Door' %}
        <img src="{{ site.baseurl }}{{ image.path }}" alt="image" />
    {% endif %}
{% endfor %}
</div>
