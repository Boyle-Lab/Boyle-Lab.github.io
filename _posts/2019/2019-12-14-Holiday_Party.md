---
layout: post
status: publish
title: Lab celebrates the end of the year!
date: '2019-12-14'
external-url:
teaser: 2019/HolidayHotpot.jpg
categories:
- Events
---

The lab celebrated the end of a sucessful 2019 with a hotpot and ugly sweater party! We also celebrated winning the gingerbread house (two years in a row!) and the holiday door that tried but just didn't make it (we actually didn't try...) and runner up for funniest! Here's to continued fun and success in 2020!

<div>
{% for image in site.static_files %}
    {% if image.path contains '2019-12-14-Holiday_Hotpot' %}
        <img src="{{ site.baseurl }}{{ image.path }}" alt="image" />
    {% endif %}
{% endfor %}
</div>
