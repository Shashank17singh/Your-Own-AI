// Unit tests for the vector search engine. Run with: ctest --output-on-failure
#include <cmath>
#include <iostream>
#include <string>
#include <vector>

#include "request_guard.h"
#include "vector_engine.h"

static int failures = 0;

#define CHECK(condition)                                                    \
    do {                                                                    \
        if (!(condition)) {                                                 \
            std::cout << "FAILED line " << __LINE__ << ": " #condition "\n"; \
            failures++;                                                     \
        }                                                                   \
    } while (0)

static bool near(float a, float b) { return std::fabs(a - b) < 1e-5f; }

static void testDistances() {
    std::vector<float> a = {1, 0}, b = {0, 1}, c = {3, 4}, origin = {0, 0};

    CHECK(near(euclidean(origin, c), 5.0f));
    CHECK(near(manhattan(origin, c), 7.0f));
    CHECK(near(cosine(a, a), 0.0f));
    CHECK(near(cosine(a, b), 1.0f));
    CHECK(near(cosine(origin, a), 1.0f));  // A zero vector must not divide by zero.
}

static void testMetricLookup() {
    std::vector<float> origin = {0, 0}, c = {3, 4};

    CHECK(near(getDistFn("manhattan")(origin, c), 7.0f));
    CHECK(near(getDistFn("unknown")(origin, c), 5.0f));  // Falls back to Euclidean.
}

static void fill(VectorDB &db, int count) {
    auto dist = getDistFn("euclidean");
    for (int i = 0; i < count; i++) {
        db.insert("item" + std::to_string(i), "cat", {(float)i, (float)i}, dist);
    }
}

static void testEveryAlgorithmFindsTheNearestItem() {
    VectorDB db(2);
    fill(db, 40);

    for (const std::string algo : {"bruteforce", "kdtree", "hnsw"}) {
        auto out = db.search({20.1f, 20.1f}, 1, "euclidean", algo);
        CHECK(out.hits.size() == 1);
        CHECK(!out.hits.empty() && out.hits[0].meta == "item20");
        CHECK(out.algo == algo);
    }
}

static void testResultsAreLimitedToK() {
    VectorDB db(2);
    fill(db, 10);

    CHECK(db.search({0, 0}, 3, "euclidean", "bruteforce").hits.size() == 3);
}

static void testRemoveTakesAnItemOutOfEveryIndex() {
    VectorDB db(2);
    fill(db, 20);

    auto nearest = db.search({5, 5}, 1, "euclidean", "bruteforce").hits[0].id;
    CHECK(db.remove(nearest));
    CHECK(!db.remove(nearest));
    CHECK(db.size() == 19);

    for (const std::string algo : {"bruteforce", "kdtree", "hnsw"}) {
        auto out = db.search({5, 5}, 1, "euclidean", algo);
        CHECK(!out.hits.empty() && out.hits[0].id != nearest);
    }
}

static void testEmptySearch() {
    VectorDB db(2);

    for (const std::string algo : {"bruteforce", "kdtree", "hnsw"}) {
        CHECK(db.search({1, 1}, 3, "euclidean", algo).hits.empty());
    }
}

static void testParseVec() {
    auto values = parseVec("1.5,abc,2");

    CHECK(values.size() == 2);  // Bad tokens are skipped.
    CHECK(!values.empty() && near(values[0], 1.5f));
    CHECK(parseVec("").empty());
}

static void testJsonHelpers() {
    CHECK(jS("say \"hi\"") == "\"say \\\"hi\\\"\"");
    CHECK(extractStr("{\"title\":\"Notes\"}", "title") == "Notes");
    CHECK(extractStr("{\"title\":\"Notes\"}", "missing").empty());
    CHECK(extractInt("{\"k\": 7}", "k") == 7);
    CHECK(extractInt("{\"k\": \"x\"}", "k", 3) == 3);
    CHECK(extractInt("{}", "k", 5) == 5);
}

static void testChunking() {
    CHECK(chunkText("").empty());
    CHECK(chunkText("short text").size() == 1);

    std::string text;
    for (int i = 0; i < 10; i++) {
        text += "w" + std::to_string(i) + " ";
    }
    auto chunks = chunkText(text, 4, 1);

    CHECK(chunks.size() == 3);
    CHECK(!chunks.empty() && chunks[0] == "w0 w1 w2 w3");
    CHECK(chunks.size() > 1 && chunks[1].rfind("w3 ", 0) == 0);  // Chunks overlap.
    CHECK(!chunks.empty() && chunks.back().find("w9") != std::string::npos);
}

static void testRequestGuard() {
    CHECK(isLocalRequest("localhost:8080", ""));
    CHECK(isLocalRequest("127.0.0.1:8080", "http://127.0.0.1:8080"));
    CHECK(isLocalRequest("localhost:8080", "http://localhost:8080"));

    CHECK(!isLocalRequest("localhost:8080", "https://evil.example"));
    CHECK(!isLocalRequest("localhost:8080", "null"));
    CHECK(!isLocalRequest("evil.example:8080", ""));  // DNS rebinding.
    CHECK(!isLocalRequest("evil.example:8080", "http://evil.example:8080"));
    CHECK(!isLocalRequest("", ""));
}

int main() {
    testDistances();
    testMetricLookup();
    testEveryAlgorithmFindsTheNearestItem();
    testResultsAreLimitedToK();
    testRemoveTakesAnItemOutOfEveryIndex();
    testEmptySearch();
    testParseVec();
    testJsonHelpers();
    testChunking();
    testRequestGuard();

    if (failures == 0) {
        std::cout << "All vector engine tests passed.\n";
    }
    return failures == 0 ? 0 : 1;
}
