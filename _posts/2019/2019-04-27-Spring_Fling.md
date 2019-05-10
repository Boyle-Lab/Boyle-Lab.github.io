---
layout: post
status: publish
title: The lab celebrated spring with Make-Your-Own-Pizza!
date: '2019-04-27'
external-url:
teaser: 2019/SpringFling.jpg
categories:
- Events
---

The lab celebrated spring by having a Make-Your-Own-Pizza party. Everyone brought their favorite toppings to share and lots of laughs, games and fun were had.

<div>
{% for image in site.static_files %}
    {% if image.path contains '2019-04-27-Spring_Fling' %}
        <img src="{{ site.baseurl }}{{ image.path }}" alt="image" />
    {% endif %}
{% endfor %}
</div>
