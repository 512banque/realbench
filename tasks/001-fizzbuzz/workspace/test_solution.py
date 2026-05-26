from solution import fizzbuzz


def test_one():
    assert fizzbuzz(1) == "1"


def test_two():
    assert fizzbuzz(2) == "2"


def test_three():
    assert fizzbuzz(3) == "Fizz"


def test_five():
    assert fizzbuzz(5) == "Buzz"


def test_six():
    assert fizzbuzz(6) == "Fizz"


def test_ten():
    assert fizzbuzz(10) == "Buzz"


def test_fifteen():
    assert fizzbuzz(15) == "FizzBuzz"


def test_thirty():
    assert fizzbuzz(30) == "FizzBuzz"


def test_seven():
    assert fizzbuzz(7) == "7"
