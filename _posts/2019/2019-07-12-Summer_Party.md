---
layout: post
status: publish
title: The lab celebrates the summer with a BBQ!
date: '2019-07-12'
external-url:
teaser: 2019/SummerParty.png
categories:
- Events
---

The lab celebrated new papers being accepted and the summer by having our annual BBQ. Lawn games and BBQ as well as lots of fun sides results in a great time had by all!

<div>
{% for image in site.static_files %}
    {% if image.path contains 'Summer_Party' %}
        <img src="{{ site.baseurl }}{{ image.path }}" alt="image" />
    {% endif %}
{% endfor %}
</div>
