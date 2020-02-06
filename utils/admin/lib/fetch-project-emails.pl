#!/usr/bin/env perl
# --------------------------------------------------------------------------------
# This file is part of the IDA research data storage service
#
# Copyright (C) 2019 Ministry of Education and Culture, Finland
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License,
# or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
# or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero General Public
# License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
# @author   CSC - IT Center for Science Ltd., Espoo Finland <servicedesk@csc.fi>
# @license  GNU Affero General Public License, version 3
# @link     https://research.csc.fi/
# --------------------------------------------------------------------------------
# This script, if executed in an environment where an LDAP server is accessible
# which conforms to the data models employed by CSC for project and user management,
# will retrieve and output the email addresses for all users associated with the
# specified project. It is utilized by various admin scripts for sending automated
# emails to project users regarding actions and events pertaining to the project.

use strict;
use warnings;

# To install NET:LDAP dependency, run: sudo yum install perl-LDAP 
# Perl ldap docs: https://metacpan.org/pod/distribution/perl-ldap/lib/Net/LDAP.pod

use Net::LDAPS;
use Net::LDAP::Util qw(ldap_error_text);

# --------------------------------------------------------------------------------

# The following LDAP_* environment variable values must be defined in the 
# environment within which the script is run, and must agree with the values
# which are configured in the Nextcloud UI Admin settings for LDAP Data, in
# the SSO & SAML authentication settings view.

if (!$ENV{'LDAP_HOST_URL'}) {
    die "Error: The environment variable LDAP_HOST_URL is not defined!\n";    
}

if (!$ENV{'LDAP_BIND_USER'}) {
    die "Error: The environment variable LDAP_BIND_USER is not defined!\n";    
}

if (!$ENV{'LDAP_PASSWORD'}) {
    die "Error: The environment variable LDAP_PASSWORD is not defined!\n";    
}

if (!$ENV{'LDAP_SEARCH_BASE'}) {
    die "Error: The environment variable LDAP_SEARCH_BASE is not defined!\n";    
}

my $ldap;
my $result;
my $project;
my $entry;
my @entries;
my $entry2;
my @entries2;
my $members;
my $member;
my $mail;

# --------------------------------------------------------------------------------

if (@ARGV != 1 ) {
    die "Usage:\t$0 <project>\n\nE.g.\t$0 2000142\n";    
}

$project = $ARGV[0];

# Connect to ldap.
$ldap = connect_to_ldap($ENV{'LDAP_BIND_USER'}, $ENV{'LDAP_PASSWORD'}, $ENV{'LDAP_HOST_URL'});

# Search for given CSC project and fetch project members.
$result = $ldap->search    (
                base   => 'ou=projects,' . $ENV{'LDAP_SEARCH_BASE'},
                scope  => 'sub',
                filter => "(&(objectClass=CSCProject)(CSCPrjNum=$project))",
                attrs => ['member']
            );

# Exit if search failed with error.
$result->code && die $result->error;

# Process the search results.
if( $result->count eq 0) {
    die "Error: Did not find project $project in LDAP.\n";
}
else {
    # Iterate over returned projects.
    @entries = $result->entries;
    foreach $entry ( @entries ) {
        # The returned members are dn links to user objects in ldap.
        $members = $entry->get_value('member', asref => 1);
        if ($members) {
            # Iterate over member dn links and do a ldap search to fetch relevant information from the user objects.
            # Change filter to '(&(objectClass=InetOrgPerson))' if you want to include disabled accounts in the search results.
            foreach $member (@$members) {
                $result = $ldap->search    (
                                base   => "$member",
                                scope  => 'base',
                                filter => '(&(objectClass=InetOrgPerson)(!(nsaccountlock=true)))',
                                attrs  => ['mail']
                            );

                # Iterate over user object search results and fetch the mail attribute.
                @entries2 = $result->entries;
                foreach $entry2 ( @entries2 ) {
                    $mail = $entry2->get_value('mail');
                    print "$mail\n";
                }
            }
        }
    }
}

# --------------------------------------------------------------------------------
# connect_to_ldap subroutine
#
# Wrapper function for setting up the ldap(s) connection.
#
# Input:   $bindDn       = dn of the user used in the bind operation.
#          $bindPassword = password of the user used in the bind operation.
#          $host         = hostname or ldap url of the ldap server.
# --------------------------------------------------------------------------------

sub connect_to_ldap {
    my ($bindDn, $bindPassword, $host) = @_;

    if (!$bindDn) {
        die "Error: bindDn missing.";
        }

    if (!$bindPassword) {
        die "Error: bindPassword missing.";
    }

    if (!$host) {
        die "Error: host missing.";
    }

    my $ldap = Net::LDAPS->new ( $host ) or die "$@";

    my $mesg = $ldap->bind ( "$bindDn",
                 password => "$bindPassword",
                 version => 3
                   );
    if ($mesg->code) {
        die ldap_error_text($mesg->code);
    }

    return $ldap;
}

