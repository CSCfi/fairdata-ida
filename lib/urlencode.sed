#--------------------------------------------------------------------------------
# This file is part of the IDA research data storage service
#
# Copyright (C) 2018 Ministry of Education and Culture, Finland
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
#--------------------------------------------------------------------------------
# sed patterns for url encoding
s:%:%25:g
s: :%20:g
s:+:%2b:g
s:<:%3c:g
s:>:%3e:g
s:#:%23:g
s:{:%7b:g
s:}:%7d:g
s:|:%7c:g
s:\\:%5c:g
s:\^:%5e:g
s:~:%7e:g
s:\[:%5b:g
s:\]:%5d:g
s:`:%60:g
s:;:%3b:g
s:/:%2f:g
s:?:%3f:g
s^:^%3a^g
s:@:%40:g
s:=:%3d:g
s:&:%26:g
s:\$:%24:g
s:\!:%21:g
s:\*:%2A:g