#!/usr/bin/env ruby
# frozen_string_literal: true

# Run from the repository root:
#   bundle exec ruby tests/test_member_role_dates.rb
# This renders the actual history template, not a reimplementation of its logic.
require 'cgi'
require 'date'

begin
  require 'liquid'
rescue LoadError
  warn "Liquid is not installed. Run bundle install, then bundle exec ruby #{__FILE__}."
  exit 1
end

root = File.expand_path('..', __dir__)
source = File.read(File.join(root, '_layouts', 'member.html'), encoding: 'UTF-8')
status_source = source[/\{% assign is_current = false %\}.*?(?=<div id="main-wrap">)/m]
history_source = source[/\{% assign prior_role_count = page\.prior_lab_roles \| size %\}.*?(?=\{% if page\.social\.email)/m]
abort 'Could not locate the status assignments and history section in member.html.' unless status_source && history_source

# These sections use standard Liquid filters only, so the full Jekyll site and
# unrelated header, footer, and publication includes are not required.
template = Liquid::Template.parse(status_source + history_source, error_mode: :strict)

def profile(dates: {}, prior_roles: nil, status: ['current'], position: 'Research Scientist', title: nil)
  data = { 'status' => status, 'position' => position, 'title' => title, 'dates' => dates }
  data['prior_lab_roles'] = prior_roles unless prior_roles.nil?
  data
end

def prior_role(end_date = nil, **options)
  { 'position' => 'Ph.D. student', 'start' => '2020-09-01', 'end' => end_date }.merge(options.transform_keys(&:to_s))
end

def plain_text(html)
  CGI.unescapeHTML(html.gsub(/<[^>]*>/, ' ').gsub(/\s+/, ' ').strip)
end

cases = [
  ['single role uses original joining date',
   profile(dates: { 'start' => '2023-08-01' }), 'Research Scientist Since August 2023'],
  ['empty prior-role list uses original joining date',
   profile(dates: { 'start' => '2023-08-01' }, prior_roles: []), 'Research Scientist Since August 2023'],
  ['explicit current-role start overrides previous end and original start',
   profile(dates: { 'start' => '2020-09-01', 'current_role_start' => '2023-08-01' },
           prior_roles: [prior_role('2023-03-30')]), 'Research Scientist Since August 2023'],
  ['explicit current-role start works without prior roles',
   profile(dates: { 'start' => '2020-09-01', 'current_role_start' => '2023-08-01' }),
   'Research Scientist Since August 2023'],
  ['previous-role end is the default',
   profile(dates: { 'start' => '2020-09-01' }, prior_roles: [prior_role('2023-08-31')]),
   'Research Scientist Since August 2023'],
  ['latest end wins even when listed first',
   profile(dates: { 'start' => '2020-09-01' }, prior_roles: [prior_role('2025-10-06'), prior_role('2023-03-30')]),
   'Research Scientist Since October 2025'],
  ['latest end wins when listed last',
   profile(dates: { 'start' => '2020-09-01' }, prior_roles: [prior_role('2023-03-30'), prior_role('2025-10-06')]),
   'Research Scientist Since October 2025'],
  ['calendar order spans years',
   profile(prior_roles: [prior_role('2025-12-31'), prior_role('2026-01-01')]),
   'Research Scientist Since January 2026'],
  ['blank explicit start falls back',
   profile(dates: { 'current_role_start' => '' }, prior_roles: [prior_role('2023-08-01')]),
   'Research Scientist Since August 2023'],
  ['null explicit start falls back',
   profile(dates: { 'current_role_start' => nil }, prior_roles: [prior_role('2023-08-01')]),
   'Research Scientist Since August 2023'],
  ['whitespace-only explicit start falls back',
   profile(dates: { 'current_role_start' => '   ' }, prior_roles: [prior_role('2023-08-01')]),
   'Research Scientist Since August 2023'],
  ['empty and missing prior end dates are ignored',
   profile(prior_roles: [prior_role(nil), prior_role(''), prior_role('   '), prior_role('2023-08-01')]),
   'Research Scientist Since August 2023'],
  ['undated prior roles do not reuse the first lab-joining date',
   profile(dates: { 'start' => '2020-09-01' }, prior_roles: [prior_role(nil)]),
   'Research Scientist Current'],
  ['missing dates retain the status label', profile, 'Research Scientist Current'],
  ['multiple membership statuses preserve the current role',
   profile(status: %w[current phd_alumni], prior_roles: [prior_role('2023-03-30')]),
   'Research Scientist Since March 2023'],
  ['legacy scalar current status is still supported',
   profile(status: 'current', dates: { 'start' => '2023-08-01' }), 'Research Scientist Since August 2023'],
  ['YAML-style Date objects are supported',
   profile(dates: { 'start' => Date.new(2020, 9, 1) },
           prior_roles: [prior_role(Date.new(2023, 8, 31)), prior_role(Date.new(2023, 7, 1))]),
   'Research Scientist Since August 2023'],
  ['explicit YAML-style Date object is supported',
   profile(dates: { 'current_role_start' => Date.new(2023, 8, 1) }, prior_roles: [prior_role('2023-03-30')]),
   'Research Scientist Since August 2023'],
  ['staff title display is preserved',
   profile(position: 'Staff', title: 'Lab Manager', dates: { 'start' => '2014-10-20' }),
   'Lab Manager Since October 2014'],
  ['alumni do not acquire a current-role entry',
   profile(status: ['alumni'], dates: { 'start' => '2020-09-01', 'end' => '2023-08-31' }), nil],
  ['doctoral alumni retain completed history only',
   profile(status: ['phd_alumni'], prior_roles: [prior_role('2023-08-31')]), nil]
]

failures = []
cases.each do |name, data, expected|
  begin
    before = Marshal.dump(data)
    html = template.render!({ 'page' => data }, strict_filters: true)
    row = html[/<li class="member-profile-history-current">(.*?)<\/li>/m, 1]
    actual = row && plain_text(row)
    raise "Expected #{expected.inspect}; received #{actual.inspect}" unless actual == expected
    raise 'Rendering changed the profile data.' unless Marshal.dump(data) == before
    if name == 'alumni do not acquire a current-role entry'
      raise 'Alumni dates changed.' unless plain_text(html).include?('September 2020–August 2023')
    elsif name == 'doctoral alumni retain completed history only'
      raise 'Completed-role history changed.' unless plain_text(html).include?('Ph.D. student September 2020–August 2023')
    elsif name == 'explicit current-role start overrides previous end and original start'
      raise 'The completed role was changed.' unless plain_text(html).include?('Ph.D. student September 2020–March 2023')
    end
    puts "PASS: #{name}"
  rescue StandardError => e
    failures << "#{name}: #{e.class}: #{e.message}"
    warn "FAIL: #{failures.last}"
  end
end

puts "#{cases.length - failures.length}/#{cases.length} regression checks passed."
exit(failures.empty? ? 0 : 1)
