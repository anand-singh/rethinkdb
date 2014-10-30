// Copyright 2010-2014 RethinkDB, all rights reserved.
#ifndef RDB_PROTOCOL_ARTIFICIAL_TABLE_BACKEND_HPP_
#define RDB_PROTOCOL_ARTIFICIAL_TABLE_BACKEND_HPP_

#include <string>
#include <vector>

#include "rdb_protocol/datum.hpp"
#include "rdb_protocol/datum_stream.hpp"

/* `artificial_table_backend_t` is the interface that `artificial_table_t` uses to access
the actual data or configuration. There is one subclass for each table like
`rethinkdb.table_config`, `rethinkdb.table_status`, and so on. */

class artificial_table_backend_t : public home_thread_mixin_t {
public:
    /* Notes:
     1. `read_all_rows_as_*()`, `read_row()`, and `write_row()` all return `false` and
        set `*error_out` if an error occurs. Note that if a row is absent in
        `read_row()`, this doesn't count as an error.
     2. If `write_row()` is called concurrently with `read_row()` or
        `read_all_rows_as_*()`, it is undefined whether the read will see the write or
        not.
     3. `get_primary_key_name()`, `read_all_rows_as_*()`, `read_row()` and `write_row()`
        can be called on any thread. */

    /* Returns the name of the primary key for the table. The return value must not
    change. This must not block. */
    virtual std::string get_primary_key_name() = 0;

    /* `read_all_rows_as_*()` returns the full dataset either as a stream or as a vector
       depending on the version being called. Subclasses should override one or the
       other, but not both. The `artificial_table_t` will only ever call
       `read_all_rows_as_stream()`; the default implementation of
       `read_all_rows_as_stream()` calls `read_all_rows_as_vector()`, while the default
       implementation of `read_all_row_as_vector()` crashes. So it will work correctly
       no matter which one the subclass overrides. The default implemention of
       `read_all_rows_as_stream()` will also take care of the filtering and sorting,
       which you must handle yourself when overriding it. */
    virtual bool read_all_rows_as_stream(
        const ql::protob_t<const Backtrace> &bt,
        const datum_range_t &range,
        sorting_t sorting,
        signal_t *interruptor,
        counted_t<ql::datum_stream_t> *rows_out,
        std::string *error_out);

    virtual bool read_all_rows_as_vector(
        signal_t *interruptor,
        std::vector<ql::datum_t> *rows_out,
        std::string *error_out);

    /* Sets `*row_out` to the current value of the row, or an empty `datum_t` if no such
    row exists. */
    virtual bool read_row(
        ql::datum_t primary_key,
        signal_t *interruptor,
        ql::datum_t *row_out,
        std::string *error_out) = 0;

    /* Called when the user issues a write command on the row. Calling `write_row()` on a
    row that doesn't exist means an insertion; calling `write_row` with
    `*new_value_inout` an empty `datum_t` means a deletion. `pkey_was_autogenerated` will
    be set to `true` only if `primary_key` is a newly-generated UUID created for the
    purpose of this insert. If the backend makes additional changes to the row before
    inserting it (such as filling in omitted fields) then it can write to
    `*new_value_inout`, but it cannot change an empty datum to a non-empty datum or vice
    versa. */
    virtual bool write_row(
        ql::datum_t primary_key,
        bool pkey_was_autogenerated,
        ql::datum_t *new_value_inout,
        signal_t *interruptor,
        std::string *error_out) = 0;

    /* RSI(reql_admin): Support change feeds. */

protected:
    virtual ~artificial_table_backend_t() { }
};

#endif /* RDB_PROTOCOL_ARTIFICIAL_TABLE_BACKEND_HPP_ */

