#pragma once

#include <iomanip>
#include <sstream>

namespace hoi5 {

inline std::string formatAmount(double number) {
    std::ostringstream out;
    if (number >= 1e6) out << std::fixed << std::setprecision(1) << number/1e6 << "M";
    else if (number >= 1e3) out << std::fixed << std::setprecision(1) << number/1e3 << "K";
    else out << std::fixed << std::setprecision(0) << number;
    return out.str();
}

}
