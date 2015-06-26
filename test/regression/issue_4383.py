#!/usr/bin/env python
# Copyright 2014 RethinkDB, all rights reserved.

from __future__ import print_function

import os, pprint, sys, time, traceback

startTime = time.time()

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir, 'common')))
import driver, scenario_common, utils, vcoptparse

op = vcoptparse.OptParser()
scenario_common.prepare_option_parser_mode_flags(op)
_, command_prefix, serve_options = scenario_common.parse_mode_flags(op.parse(sys.argv))

r = utils.import_python_driver()

print("Starting cluster of two servers (%.2fs)" % (time.time() - startTime))
with driver.Metacluster() as metacluster:
    cluster = driver.Cluster(metacluster)
    files_a = driver.Files(metacluster, "a", db_path="a_data",
        command_prefix=command_prefix, console_output=True)
    files_b = driver.Files(metacluster, "b", db_path="b_data",
        command_prefix=command_prefix, console_output=True)
    server_a_1 = driver.Process(cluster, files_a,
        command_prefix=command_prefix, extra_options=serve_options,
        console_output=True, wait_until_ready=True)
    server_b_1 = driver.Process(cluster, files_b,
        command_prefix=command_prefix, extra_options=serve_options,
        console_output=True, wait_until_ready=True)
    conn = r.connect(host=server_a_1.host, port=server_a_1.driver_port)

    print("Creating a table (%.2fs)" % (time.time() - startTime))
    r.db_create("test").run(conn)
    r.db("rethinkdb").table("table_config").insert({
        "name": "test",
        "db": "test",
        "shards": [{"primary_replica": "a", "replicas": ["a"]}] * 16
        }).run(conn)
    r.table("test").wait().run(conn)

    total_docs = 100000
    print("Inserting %d documents (%.2fs)" % (total_docs, time.time() - startTime))
    docs_so_far = 0
    while docs_so_far < total_docs:
        chunk = min(total_docs - docs_so_far, 1000)
        res = r.table("test").insert(r.range(chunk).map({
            "value": r.row,
            "padding": "x" * 100
            }), durability="soft").run(conn)
        assert res["inserted"] == chunk
        docs_so_far += chunk
        print("Progress: %d/%d (%.2fs)" % (docs_so_far, total_docs, time.time() - startTime))

    print("Beginning replication to second server (%.2fs)" % (time.time() - startTime))
    r.table("test").config().update({
        "shards": [{"primary_replica": "a", "replicas": ["a", "b"]}] * 16
        }).run(conn)
    status = r.table("test").status().run(conn)
    assert status["status"]["ready_for_writes"], status

    print("Shutting down both servers (%.2fs)" % (time.time() - startTime))
    server_a_1.check_and_stop()
    server_b_1.check_and_stop()

    print("Restarting both servers (%.2fs)" % (time.time() - startTime))
    server_a_2 = driver.Process(cluster, files_a,
        command_prefix=command_prefix, extra_options=serve_options,
        console_output=True, wait_until_ready=True)
    server_b_2 = driver.Process(cluster, files_b,
        command_prefix=command_prefix, extra_options=serve_options,
        console_output=True, wait_until_ready=True)
    conn_a = r.connect(host=server_a_2.host, port=server_a_2.driver_port)
    conn_b = r.connect(host=server_b_2.host, port=server_b_2.driver_port)

    print("Checking that table is available for writes (%.2fs)" % (time.time() - startTime))
    try:
        r.table("test").wait(wait_for="ready_for_writes", timeout=10).run(conn_a)
    except RqlRuntimeError, e:
        status = r.table("test").status().run(conn_a)
        pprint.pprint(status)
        raise
    try:
        r.table("test").wait(wait_for="ready_for_writes", timeout=10).run(conn_b)
    except RqlRuntimeError, e:
        status = r.table("test").status().run(conn_b)
        pprint.pprint(status)
        raise

    print("Making sure the backfill didn't end (%.2fs)" % (time.time() - startTime))
    status = r.table("test").status().run(conn_a)
    assert not status["status"]["all_replicas_ready"], status

    print("Cleaning up (%.2fs)" % (time.time() - startTime))
print("Done. (%.2fs)" % (time.time() - startTime))