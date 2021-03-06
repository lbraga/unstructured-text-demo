# Copyright 2016 Google, Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Custom Readers."""

from apache_beam.io import filebasedsource


def _iterable_gcs(f):
    """Create an generator for a not-quite-filelike object.

    FileBasedSource.open_file returns an object that doesn't implement the file
    interface completely, so we need this utility function in order to iterate
    over lines, while keeping the .tell() accurate.
    """
    while True:
        line = f.readline()
        if not line:
            break
        yield line


class XmlFileSource(filebasedsource.FileBasedSource):
    """A Beam source for XML that emits all instances of the given element.

    A custom source is necessary to enable parallelization of processing for the
    elements. The existing TextFileSource emits lines, but the Wikipedia XML
    dump is a giant XML file, where elements span multiple lines.
    """
    def __init__(self, element, *args, **kwargs):
        super(XmlFileSource, self).__init__(*args, **kwargs)
        self.open_tag = '<{}>'.format(element)
        self.close_tag = '</{}>'.format(element)

    def read_records(self, file_name, offset_range_tracker):
        return self.tag_iterator(file_name, offset_range_tracker)

    def tag_iterator(self, file_name, offset_range_tracker):
        with self.open_file(file_name) as f:
            f.seek(offset_range_tracker.start_position() or 0)

            iterable_f = _iterable_gcs(f)

            while True:
                current_pos = f.tell()
                # First, look for the start of a tag
                # If we hit the end of the range allotted to us without finding
                # an element, stop.
                for line in iterable_f:
                    if self.open_tag in line:
                        if not offset_range_tracker.try_claim(current_pos):
                            raise StopIteration()
                        content = [line]
                        break
                    current_pos = f.tell()
                else:
                    # We ran off the end of the file without finding the tag.
                    # This means we're done.
                    raise StopIteration()

                # We're in a tag. Collect its contents and emit it.
                for line in iterable_f:
                    content.append(line)
                    if self.close_tag in line:
                        yield ''.join(content)
                        break
